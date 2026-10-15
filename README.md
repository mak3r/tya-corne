# tya-corne

ZMK firmware for my **Typeractive Corne**: a wireless split Corne with a nice!nano v2 and a nice!view on each half. No LEDs, no encoders. It runs the same `mak3r` layout as my wired Halcyon Corne ([`mak3r/halcyon-corne`](https://github.com/mak3r/halcyon-corne), QMK/Vial), and it feeds the [`corne-kbd-hud`](https://github.com/mak3r/corne-kbd-hud) desktop overlay over USB or Bluetooth.

## Builds

Every push builds these with GitHub Actions. Download them from the run's **Artifacts**.

| Artifact | Flash to |
|---|---|
| `tya_corne_wireless_left_niceview` | left half (the half that pairs with the computer; HUD broadcast lives here) |
| `tya_corne_wireless_right_niceview` | right half |
| `tya_corne_settings_reset` | both halves, only to wipe pairing state (then reflash the real firmware) |

**Flashing:** plug a half in over USB and double-tap its reset button. A `NICENANO` drive appears; copy the matching `.uf2` onto it. Do the right half first, then the left.

**Halves won't talk to each other / pairing is wedged:**
1. Flash `settings_reset` to both halves.
2. Flash the real firmware again.
3. Reset both halves at the same time.
4. Remove the old keyboard pairing on the computer and pair again.

## Layout

`config/corne.keymap` and `src/hud_keymap.inc` are **generated** from the Halcyon's `keymap.json`. Don't edit them by hand:

```bash
python3 scripts/generate_keymap.py \
    ../halcyon-corne/keyboards/splitkb/halcyon/corne/keymaps/mak3r/keymap.json
```

**The layout is identical to the Halcyon's.** Keys that one board can't use do nothing on that board:

- **Layer 3:** the RGB keys do nothing here (no LEDs).
- **Layer 5** (reached with `TG(5)` on layer 3, left with either middle thumb). These keys do nothing on the Halcyon:
  - top-left: USB/Bluetooth output toggle
  - left middle-row outer key: clear the current profile's pairing
  - bottom row, first five keys: Bluetooth profiles 0–4
- **Layer 4 (Mouse)** is the same on both boards:
  - A / ;: left / right click; S and L: middle click
  - D / F / J / K: pointer down / right / left / up
  - E / R / U / I: scroll right / down / up / left
  - right outer column, top / middle / bottom: lock the pointer speed slow / medium / fast. Tap the same key again to go back to the normal speed-up. ZMK has no speed keys, so each one turns on a hidden speed layer (layers 8–10) that scales `&mmv`. Leaving the mouse layer with the left middle thumb (`TO(0)`) also unlocks the speed.
  - right middle thumb: `MO(2)`, as on the base layer, for switching workspaces
  - T: sends F13, which is the Halcyon's drag-to-scroll toggle and harmless here

There's one shared layout file, halcyon-corne's `keymap.json`. It contains the Bluetooth keys too (`OUT_TOG`, `BT_CLR`, `BT_SEL_0`–`4`); the Halcyon defines them as `KC_NO`.

## HUD

The left half exposes a raw HID interface (via [`zzeneg/zmk-raw-hid`](https://github.com/zzeneg/zmk-raw-hid)) set up to look exactly like QMK's console interface. `src/hud_broadcast.c` sends the same `LAYER:<n>` / `KEY:<row>,<col>,<0|1>` lines as the Halcyon, in the Halcyon's row/col numbering. So `corne-kbd-hud` works over USB or Bluetooth.

The HUD can also ask the keyboard for its keymap (it writes `MAP?`). The left half answers with one `MAP:` line per key, so the HUD shows this board's actual keys. `generate_keymap.py` writes that table (`src/hud_keymap.inc`) along with `corne.keymap`.

## Building locally

See `CLAUDE.md` ("Local build").
