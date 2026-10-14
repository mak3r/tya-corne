#!/usr/bin/env python3
"""Generate config/corne.keymap (the "mak3r" keymap) from halcyon-corne's
QMK keymap.json, so this board's layout stays in sync with the Halcyon's.

Usage (from this repo's root):
    python3 scripts/generate_keymap.py \\
        ../halcyon-corne/keyboards/splitkb/halcyon/corne/keymaps/mak3r/keymap.json

What it does:
- Keeps the first 42 entries of each layer (3x12 keys + 6 thumbs). They are
  in the same order as ZMK's corne key positions 0-41. Drops the Halcyon
  module row (the last 10 entries) and the encoder map.
- Translates each QMK keycode to a ZMK binding via the tables below. An
  unknown keycode is an error. Add it to a table instead of guessing.
- keymap.json is the single layout shared by both boards. It holds every
  key either board can do; each board turns the ones it can't do into a
  no-op. Here that's the Halcyon's RGB keys (UNSUPPORTED_HERE -> &none).
  The Halcyon does the same for the Bluetooth/output keys (OUT_TOG, BT_CLR,
  BT_SEL_n), which are #defined to KC_NO in its config.h. Only keycodes
  listed as known-but-unsupported become no-ops: anything else that doesn't
  translate (a typo, say) is still an error.
"""

import json
import re
import sys
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "config" / "corne.keymap"
KEY_COUNT = 42
LAYER_NAMES = ["Base", "Symbols", "Nav", "Function", "Mouse", "Return2", "Unused6", "Unused7"]

# QMK basic keycode (without "KC_") -> ZMK key name, for names that differ.
# Letters, F-keys, and names that are identical in both (TAB, LEFT, ...) fall
# through unchanged -- see translate_basic().
BASIC = {
    "BSPC": "BSPC", "ESCAPE": "ESC", "ENTER": "RET", "SPACE": "SPACE",
    "SCLN": "SEMI", "QUOTE": "SQT", "COMMA": "COMMA", "DOT": "DOT", "SLASH": "FSLH",
    "GRAVE": "GRAVE", "BSLS": "BSLH", "LBRC": "LBKT", "RBRC": "RBKT",
    "MINUS": "MINUS", "EQUAL": "EQUAL", "DELETE": "DEL",
    "LSFT": "LSHFT", "RSFT": "RSHFT", "LCTL": "LCTRL", "RCTL": "RCTRL",
    "LALT": "LALT", "RALT": "RALT", "LGUI": "LGUI", "RGUI": "RGUI",
    "PGDN": "PG_DN", "PGUP": "PG_UP", "HOME": "HOME", "END": "END",
    "KP_MINUS": "KP_MINUS", "KP_EQUAL": "KP_EQUAL", "KP_DOT": "KP_DOT",
    "VOLD": "C_VOL_DN", "VOLU": "C_VOL_UP", "MUTE": "C_MUTE",
    "MRWD": "C_REWIND", "MFFD": "C_FAST_FORWARD", "MPLY": "C_PLAY_PAUSE",
}
PASSTHROUGH = re.compile(r"^([A-Z]|F\d{1,2}|TAB|LEFT|RIGHT|UP|DOWN)$")

# QMK modifier-wrapper function -> ZMK modifier function(s), outermost first.
MOD_WRAPPERS = {
    "LSFT": ["LS"], "RSFT": ["RS"], "LCTL": ["LC"], "RCTL": ["RC"],
    "LALT": ["LA"], "RALT": ["RA"], "LGUI": ["LG"], "RGUI": ["RG"],
    "SGUI": ["LS", "LG"],
}

# QMK mod-tap -> ZMK hold modifier (bound via the &hm hold-tap defined below).
MOD_TAPS = {"LCTL_T": "LCTRL", "RCTL_T": "RCTRL", "LSFT_T": "LSHFT", "RSFT_T": "RSHFT",
            "LALT_T": "LALT", "RALT_T": "RALT", "LGUI_T": "LGUI", "RGUI_T": "RGUI"}

LAYER_FUNCS = {"MO": "&mo", "OSL": "&sl", "TG": "&tog", "TO": "&to"}

SIMPLE = {
    "KC_TRNS": "&trans", "KC_NO": "&none",
    "QK_BOOT": "&bootloader", "QK_CAPS_WORD_TOGGLE": "&caps_word",
    "KC_BTN1": "&mkp LCLK", "KC_BTN2": "&mkp RCLK", "KC_BTN3": "&mkp MCLK",
    "KC_MS_LEFT": "&mmv MOVE_LEFT", "KC_MS_DOWN": "&mmv MOVE_DOWN",
    "KC_MS_UP": "&mmv MOVE_UP", "KC_MS_RIGHT": "&mmv MOVE_RIGHT",
    "KC_MS_WH_LEFT": "&msc SCRL_LEFT", "KC_MS_WH_DOWN": "&msc SCRL_DOWN",
    "KC_MS_WH_UP": "&msc SCRL_UP", "KC_MS_WH_RIGHT": "&msc SCRL_RIGHT",
    # Wireless-only keycodes in the shared layout (KC_NO on the Halcyon).
    "OUT_TOG": "&out OUT_TOG", "BT_CLR": "&bt BT_CLR",
    "BT_SEL_0": "&bt BT_SEL 0", "BT_SEL_1": "&bt BT_SEL 1", "BT_SEL_2": "&bt BT_SEL 2",
    "BT_SEL_3": "&bt BT_SEL 3", "BT_SEL_4": "&bt BT_SEL 4",
}

# Real keycodes in the shared layout that this board can't do (no LEDs).
UNSUPPORTED_HERE = {"RM_TOGG", "RM_NEXT", "RM_PREV", "RM_VALU", "RM_VALD"}

def translate_basic(kc):
    if not kc.startswith("KC_"):
        raise ValueError(kc)
    name = kc[3:]
    if name in BASIC:
        return BASIC[name]
    m = re.fullmatch(r"KP_(\d)", name)
    if m:
        return f"KP_N{m.group(1)}"
    if re.fullmatch(r"\d", name):
        return f"N{name}"
    if PASSTHROUGH.match(name):
        return name
    raise ValueError(kc)


def translate(kc):
    if kc in UNSUPPORTED_HERE:
        return "&none"
    if kc in SIMPLE:
        return SIMPLE[kc]
    m = re.fullmatch(r"(\w+)\((.+)\)", kc)
    if not m:
        return f"&kp {translate_basic(kc)}"
    func, arg = m.groups()
    if func in LAYER_FUNCS:
        return f"{LAYER_FUNCS[func]} {int(arg)}"
    if func in MOD_TAPS:
        return f"&hm {MOD_TAPS[func]} {translate_basic(arg)}"
    if func in MOD_WRAPPERS:
        inner = translate_basic(arg)
        for mod in reversed(MOD_WRAPPERS[func]):
            inner = f"{mod}({inner})"
        return f"&kp {inner}"
    raise ValueError(kc)


def load_qmk_keymap(path):
    text = Path(path).read_text()
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)  # keymap.json has // comments
    return json.loads(text)


def format_layer(bindings):
    rows = [bindings[0:12], bindings[12:24], bindings[24:36]]
    width = max(len(b) for b in bindings)
    lines = []
    for row in rows:
        left = " ".join(b.ljust(width) for b in row[:6])
        right = " ".join(b.ljust(width) for b in row[6:])
        lines.append(f"{left}   {right}".rstrip())
    pad = " " * ((width + 1) * 3)
    thumbs_l = " ".join(b.ljust(width) for b in bindings[36:39])
    thumbs_r = " ".join(b.ljust(width) for b in bindings[39:42])
    lines.append(f"{pad}{thumbs_l}   {thumbs_r}".rstrip())
    return "\n".join("            " + line for line in lines)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    qmk = load_qmk_keymap(sys.argv[1])
    errors = []
    layers = []
    for li, layer in enumerate(qmk["layers"]):
        out = []
        for pos, kc in enumerate(layer[:KEY_COUNT]):
            try:
                out.append(translate(kc))
            except ValueError:
                errors.append(f"layer {li} pos {pos}: no ZMK translation for {kc}")
        layers.append(out)
    if errors:
        sys.exit("\n".join(errors))

    blocks = []
    for li, bindings in enumerate(layers):
        name = LAYER_NAMES[li] if li < len(LAYER_NAMES) else f"Layer{li}"
        blocks.append(
            f"        layer_{li} {{\n"
            f'            display-name = "{name}";\n'
            f"            bindings = <\n{format_layer(bindings)}\n            >;\n"
            f"        }};"
        )

    OUT_PATH.write_text(f"""\
/*
 * mak3r keymap for the Typeractive Corne (ZMK).
 *
 * GENERATED by scripts/generate_keymap.py from halcyon-corne's
 * keyboards/splitkb/halcyon/corne/keymaps/mak3r/keymap.json -- do not edit
 * by hand. Change the shared layout (halcyon-corne's keymap.json) and
 * regenerate.
 */

#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/bt.h>
#include <dt-bindings/zmk/outputs.h>
#include <dt-bindings/zmk/pointing.h>

/ {{
    behaviors {{
        // Home-row mod-tap (QMK LCTL_T/RCTL_T). tap-preferred + 200ms is the
        // closest match to QMK's default mod-tap behavior.
        hm: home_row_mod {{
            compatible = "zmk,behavior-hold-tap";
            #binding-cells = <2>;
            flavor = "tap-preferred";
            tapping-term-ms = <200>;
            bindings = <&kp>, <&kp>;
        }};
    }};

    keymap {{
        compatible = "zmk,keymap";

{chr(10).join(blocks)}
    }};
}};
""")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
