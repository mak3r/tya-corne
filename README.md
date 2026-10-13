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

`config/corne.keymap` is **generated** from the Halcyon's `keymap.json`. Don't edit it by hand:

```bash
python3 scripts/generate_keymap.py \
    ../halcyon-corne/keyboards/splitkb/halcyon/corne/keymaps/mak3r/keymap.json
```

Layers 0–2 and 5–7 are identical to the Halcyon. The wireless-only differences live in the script's `OVERRIDES` table:

- **Layer 3 (Function):**
  - top-left key: USB/Bluetooth output toggle (was the RGB toggle)
  - bottom row, first five keys: Bluetooth profiles 0–4 (were RGB keys)
  - left middle-row outer key: clear the current profile's pairing
- **Layer 4 (Mouse):** clicks stay on S/D/F. J/K/L/; move the pointer, and M/,/./ scroll. The A key (the Halcyon's drag-to-scroll toggle) is empty here.

## HUD

The left half exposes a raw HID interface (via [`zzeneg/zmk-raw-hid`](https://github.com/zzeneg/zmk-raw-hid)) set up to look exactly like QMK's console interface. `src/hud_broadcast.c` sends the same `LAYER:<n>` / `KEY:<row>,<col>,<0|1>` lines as the Halcyon, in the Halcyon's row/col numbering. So `corne-kbd-hud` works without any changes, over USB or Bluetooth.

## Building locally

See `CLAUDE.md` ("Local build").
