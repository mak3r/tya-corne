# CLAUDE.md — Agent Instructions

Solo hobby-hardware project: ZMK firmware for a Typeractive wireless Corne. Each half has a nice!nano v2 and a nice!view; there are no LEDs and no encoders. Claude works directly on `main`, and the human reviews before tags/releases.

## Related repos
- `~/projects/halcyon-corne` (`mak3r/halcyon-corne`): the wired Halcyon Corne, QMK/Vial. **Its `mak3r` `keymap.json` is the source of truth for this board's layout.**
- `~/projects/corne-kbd-hud` (`mak3r/corne-kbd-hud`): the desktop HUD app this board feeds.

ZMK and QMK share no code or tooling. That's why this is a sibling repo and not part of halcyon-corne.

## How it works
- Standard ZMK user-config repo (from `zmkfirmware/unified-zmk-config-template`), pinned to **ZMK v0.3** (`config/west.yml`). Board name on v0.3 is `nice_nano_v2`.
- `build.yaml` is the build matrix. `artifact-name` follows halcyon-corne's TARGET convention: `tya_corne_<connectivity>_<side>_<module>`.
- The keymap file must be named `config/corne.keymap`: ZMK finds it by shield name, and `KEYMAP_FILE` only accepts absolute paths, which don't survive CI. It's "the mak3r keymap" by its header, not its filename.
- **The keymap is generated.** `scripts/generate_keymap.py` translates the Halcyon's `keymap.json`:
  - It drops the module row and encoders. The first 42 entries per layer map 1:1 to ZMK corne positions.
  - **halcyon-corne's `keymap.json` is the single layout shared by both boards** (Mark's decision, 2026-10-14). It holds every key either board can do. Each board turns the keys it can't do into a no-op, but only keycodes it explicitly lists as known-but-unsupported:
    - here, `UNSUPPORTED_HERE` (the QMK `RM_*` RGB keys) become `&none`
    - on the Halcyon, the Bluetooth/output names (`OUT_TOG`, `BT_CLR`, `BT_SEL_0`–`4`) and the Studio unlock key (`STUDIO_UNLOCK`) are `#define`d to `KC_NO` in its `config.h`, and its `generate_keymap_from_vil.py` keeps them when a Vial export shows those spots as `KC_NO`

    Those three lists must stay in sync. There are no per-board overrides; change the shared layout instead.
  - An unknown QMK keycode is an error. Add it to the script's tables; don't hand-edit `corne.keymap`.
- This repo is also a Zephyr module (`zephyr/module.yml`, `CMakeLists.txt`, `Kconfig`) so it can ship `src/hud_broadcast.c`.

## HUD broadcast
- `zzeneg/zmk-raw-hid` adds a raw HID interface over USB **and** BLE. It's central-only, so the `raw_hid_adapter` shield is only on the left build.
- `config/corne.conf` sets its usage page/usage/report size to `0xFF31`/`0x74`/`32`, which is QMK `CONSOLE_ENABLE`'s interface. `corne-kbd-hud` matches on exactly that (not VID/PID), so it needs no changes.
- `src/hud_broadcast.c` sends `LAYER:<n>\n` and `KEY:<row>,<col>,<0|1>\n`, the same wire format as halcyon-corne's `hud_console.c`.
  - Key positions are translated into the **Halcyon's** matrix row/col (right half mirrored, thumbs on rows 3/8), so the HUD's key highlighting works unchanged.
  - Sends go through a dedicated work queue. zmk-raw-hid's USB send can block up to 30ms, which mustn't delay key processing.
- **Keymap on request.** When the HUD writes `MAP?` (an output report on the same interface), `hud_broadcast.c` replies with `MAP:<layer>,<row>,<col>,<keycode>\n` for every key, then `MAPEND:<count>\n`.
  - The keycodes are the QMK names from halcyon-corne's `keymap.json` (e.g. `LCTL_T(KC_D)`, `BT_SEL_0`), so the HUD labels both boards with the same code.
  - They come from `src/hud_keymap.inc`, which `generate_keymap.py` writes next to `corne.keymap`. There's no ZMK Studio here, so that table always matches what's running. If Studio (live remapping) is ever added, this would have to read the live bindings instead.
  - The dump runs on the same work queue and drains queued `KEY:`/`LAYER:` lines between `MAP:` lines. A `MAP?` that arrives mid-dump is ignored.
  - The generator fails if a `MAP:` line wouldn't fit in one 32-byte report.

## ZMK Studio
- Enabled on the left (central) build only: `build.yaml` adds the `studio-rpc-usb-uart` snippet and `-DCONFIG_ZMK_STUDIO=y` (Mark's request, 2026-10-14). `~/projects/zmk-build/build.sh` passes the same; keep them in sync.
- Locking is on (the default). The unlock key is `STUDIO_UNLOCK` in `keymap.json` → `&studio_unlock`, on layer 5 at the left half's top-right key.
- Studio edits live in the keyboard's settings and override the compiled keymap. That breaks two assumptions elsewhere:
  - `keymap.json` is meant to be the one layout. Studio edits aren't in it until someone copies them back.
  - `hud_keymap.inc` (what `MAP?` answers) is the compiled keymap, so the HUD shows stale labels after a Studio edit.
- Planned, not built: a script that reads the live keymap over Studio's RPC and writes it back into `keymap.json` ("bake it in"), and having `MAP?` answer from the live bindings so the HUD shows Studio edits. Both need ZMK→QMK reverse translation of `generate_keymap.py`'s tables.

## Local build
Use the container, like halcyon-corne does (`podman machine start` first). The workspace is `~/projects/zmk-build` (west checkout of ZMK v0.3 + modules, outside this repo):

```bash
podman run --rm -v ~/projects/zmk-build:/ws -v ~/projects/tya-corne:/repo \
  docker.io/zmkfirmware/zmk-build-arm:3.5 sh /ws/build.sh
```

`build.sh` builds all three targets into `~/projects/zmk-build/out/`. Per-target logs are in `build/<name>.log`. If `west.yml` changes, it re-runs `west update`.

## Commit standards
- Conventional commits: `<type>(<scope>): <description>`.
- Include `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` on commits made by Claude.
- Never reference a commit SHA without verifying it with `git rev-parse --verify <sha>`.
