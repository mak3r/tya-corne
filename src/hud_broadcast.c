/*
 * Sends the active layer and individual keystrokes to the corne-kbd-hud
 * desktop app, as the same plain text lines halcyon-corne's hud_console.c
 * sends over QMK's CONSOLE_ENABLE interface:
 *
 *   "LAYER:<n>\n"              -- highest active layer changed
 *   "KEY:<row>,<col>,<0|1>\n"  -- a key was released/pressed, in the
 *                                 *Halcyon's* matrix row/col space, so the
 *                                 HUD's per-key highlighting works unchanged
 *   "MAP:<layer>,<row>,<col>,<keycode>\n", then "MAPEND:<count>\n"
 *                              -- the whole keymap, as the QMK keycode names
 *                                 in halcyon-corne's keymap.json, sent when
 *                                 the HUD writes "MAP?" (hud_keymap.inc)
 *
 * Transport is zzeneg/zmk-raw-hid (USB and BLE), configured in corne.conf to
 * use the console usage page/usage. Central (left) half only: layer state
 * lives there, and it sees position events for both halves.
 *
 * Reports are sent from a dedicated work queue, not from the event
 * listeners: zmk-raw-hid's USB path can block for up to 30ms waiting for
 * the previous transfer, which shouldn't delay key processing.
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/keymap.h>
#include <zephyr/sys/atomic.h>

#include <raw_hid/events.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#define LINE_SIZE CONFIG_RAW_HID_REPORT_SIZE
#define KEY_COUNT 42

#include "hud_keymap.inc"

/* ZMK corne position (0-41) -> Halcyon LAYOUT_corne_hlc matrix row/col
 * (see halcyon-corne's mak3r/config.h). The right half's columns are
 * mirrored there: its innermost key (Y) is col 5, outermost (BSPC) col 0. */
static void position_to_halcyon(uint32_t pos, uint8_t *row, uint8_t *col) {
    if (pos < 36) {
        uint8_t r = pos / 12, c = pos % 12;
        if (c < 6) {
            *row = r;
            *col = c;
        } else {
            *row = r + 5;
            *col = 11 - c;
        }
    } else {
        uint8_t t = pos - 36; /* thumbs: LGUI MO1 SPC | ENT MO2 RGUI */
        if (t < 3) {
            *row = 3;
            *col = 3 + t;
        } else {
            *row = 8;
            *col = 8 - t;
        }
    }
}

K_MSGQ_DEFINE(hud_msgq, LINE_SIZE, 16, 4);

static void hud_send_report(uint8_t *line) {
    raise_raw_hid_sent_event((struct raw_hid_sent_event){.data = line, .length = LINE_SIZE});
}

static void hud_send_work_handler(struct k_work *work) {
    static uint8_t line[LINE_SIZE];
    while (k_msgq_get(&hud_msgq, line, K_NO_WAIT) == 0) {
        hud_send_report(line);
    }
}

static K_WORK_DEFINE(hud_send_work, hud_send_work_handler);

static atomic_t dump_running;

/* Runs on the same work queue as hud_send_work, so the two never send at
 * once. Drains queued LAYER:/KEY: lines between MAP: lines, so key
 * highlighting keeps up during the (BLE: several second) dump. */
static void hud_dump_work_handler(struct k_work *work) {
    uint8_t line[LINE_SIZE];
    int count = 0;
    for (int layer = 0; layer < ARRAY_SIZE(hud_keymap); layer++) {
        for (int pos = 0; pos < KEY_COUNT; pos++) {
            uint8_t row, col;
            position_to_halcyon(pos, &row, &col);
            memset(line, 0, sizeof(line));
            snprintf((char *)line, sizeof(line), "MAP:%d,%d,%d,%s\n", layer, row, col,
                     hud_keymap[layer][pos]);
            hud_send_report(line);
            count++;
            hud_send_work_handler(NULL);
        }
    }
    memset(line, 0, sizeof(line));
    snprintf((char *)line, sizeof(line), "MAPEND:%d\n", count);
    hud_send_report(line);
    atomic_clear(&dump_running);
}

static K_WORK_DEFINE(hud_dump_work, hud_dump_work_handler);
static K_THREAD_STACK_DEFINE(hud_work_stack, 1024);
static struct k_work_q hud_work_q;

static void hud_queue_line(const char *fmt, ...) {
    char line[LINE_SIZE] = {0};
    va_list args;
    va_start(args, fmt);
    vsnprintf(line, sizeof(line), fmt, args);
    va_end(args);
    if (k_msgq_put(&hud_msgq, line, K_NO_WAIT) != 0) {
        LOG_DBG("HUD queue full, dropping line");
        return;
    }
    k_work_submit_to_queue(&hud_work_q, &hud_send_work);
}

static int hud_layer_listener(const zmk_event_t *eh) {
    static int last_layer = -1;
    int layer = zmk_keymap_highest_layer_active();
    if (layer != last_layer) {
        last_layer = layer;
        hud_queue_line("LAYER:%d\n", layer);
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(hud_layer, hud_layer_listener);
ZMK_SUBSCRIPTION(hud_layer, zmk_layer_state_changed);

static int hud_position_listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *ev = as_zmk_position_state_changed(eh);
    if (ev == NULL || ev->position >= 42) {
        return ZMK_EV_EVENT_BUBBLE;
    }
    uint8_t row, col;
    position_to_halcyon(ev->position, &row, &col);
    hud_queue_line("KEY:%d,%d,%d\n", row, col, ev->state ? 1 : 0);
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(hud_position, hud_position_listener);
ZMK_SUBSCRIPTION(hud_position, zmk_position_state_changed);

/* The HUD asks for the keymap by writing "MAP?". Tolerate a leading 0x00,
 * in case a host passes the (unused) report ID through. */
static int hud_request_listener(const zmk_event_t *eh) {
    const struct raw_hid_received_event *ev = as_raw_hid_received_event(eh);
    if (ev == NULL) {
        return ZMK_EV_EVENT_BUBBLE;
    }
    const uint8_t *data = ev->data;
    uint8_t length = ev->length;
    if (length > 0 && data[0] == 0) {
        data++;
        length--;
    }
    if (length >= 4 && memcmp(data, "MAP?", 4) == 0 && atomic_cas(&dump_running, 0, 1)) {
        k_work_submit_to_queue(&hud_work_q, &hud_dump_work);
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(hud_request, hud_request_listener);
ZMK_SUBSCRIPTION(hud_request, raw_hid_received_event);

static int hud_broadcast_init(void) {
    k_work_queue_start(&hud_work_q, hud_work_stack, K_THREAD_STACK_SIZEOF(hud_work_stack),
                       K_LOWEST_APPLICATION_THREAD_PRIO, NULL);
    return 0;
}

SYS_INIT(hud_broadcast_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
