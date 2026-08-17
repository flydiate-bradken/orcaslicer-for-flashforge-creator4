# Background: how this was built, and what's still unconfirmed

This is reference material for anyone extending or debugging this project.
If you just want to install and use it, see [README.md](../README.md)
instead — nothing here is required reading for that.

## Why this exists

The Flashforge Creator 4 doesn't accept plain `.gcode`. Flashforge's own
slicer, FlashPrint 5, wraps sliced output in a proprietary binary container
(`.gx`) and the firmware expects a handful of Flashforge-specific gcode
commands in the body. Flashforge's own OrcaSlicer fork ("Orca-Flashforge" /
"Flash Studio") supports the Adventurer 5M family, AD5X, Guider 3 Ultra, and
Creator 5 — but not the Creator 4. This project fills that gap: a
post-processing script that wraps OrcaSlicer's output into the correct
`.gx` format, paired with OrcaSlicer printer/process/filament profiles that
emit the correct Flashforge-specific gcode. Everything was derived from real
FlashPrint 5 exports for the Creator 4, not guessed.

## Confirmed fix from real hardware testing

A real supervised test print caught a genuine bug that file-format analysis
alone couldn't:

**Symptom**: bed heated, nozzle heated, motion all looked normal, but the
right extruder never fed filament at all (no motor activity), despite
filament being pre-loaded and primed via the front panel beforehand.

**Root cause**: the machine profiles had `use_relative_e_distances: "1"`,
which made OrcaSlicer emit `M83` (relative extrusion) and small per-move E
deltas. A real FlashPrint export uses neither `M82` nor `M83` and its E
values climb continuously and cumulatively — the Creator 4's native/default
mode is **absolute** extrusion. If firmware doesn't honor `M83` and stays in
its default absolute mode, every one of those small relative-style E values
gets interpreted as an absolute target very close to zero — the extruder
barely moves for the entire print, matching the observed symptom exactly.

**Fix** (already applied in all machine profiles in this repo):
`use_relative_e_distances` set to `"0"`, and `before_layer_change_gcode`'s
`G92 E0` commented out (safe/expected in relative mode, but desyncs the
printer's E position from the slicer's in absolute mode).

**If you're building on this project for a different printer/firmware**:
don't assume relative-E is a safe default just because it's common in
generic Marlin profiles — check what convention the printer's own native
slicer output actually uses first.

## Open questions / known unknowns

Two real FlashPrint 5 `.gx` exports for this printer were examined while
building this project, and they disagree on a few specifics. Rather than
guess, each was resolved to a documented, conservative default — flagged
here, in [NOZZLE_VARIANT_TABLE.md](NOZZLE_VARIANT_TABLE.md), and inside each
machine profile's own `printer_notes` field (visible in OrcaSlicer's printer
settings UI). None of these affect whether the bridge *runs* — only,
potentially, exact print behavior/positioning.

1. **`M651 Sxxx` vs bare `M652`** immediately before tool-select (`M108 T0`)
   in the start gcode — `M651 Sxxx` turns the Creator 4's case/chamber fan
   **on** to speed `xxx` (0-255); bare `M652` turns it **off**. Pairs with
   item 4 below as a matched, material-dependent preset (fan off + chamber
   heat for ABS, fan on + no chamber heat for PLA). The printer profiles
   ship a material-neutral baseline (fan off, chamber heat off); the
   filament profiles layer the real material-specific pairing on top — see
   README.md "Filament profiles".
2. **A trailing field in the `.gx` binary header** — `0` in the real ABS
   sample, `257` in the real PLA sample. Best guess: `257` (`0x0101`)
   mirrors the case-fan on/off state from item 1 into the header for the
   LCD, but unconfirmed, and this project's post-processing script doesn't
   currently adjust it for the PLA fan-override case. Keeps it hardcoded at
   `0`.
3. **Bed origin** — profiles use centered coordinates (`-200,-175` to
   `200,175`), inferred from real gcode containing small, sometimes-negative
   X/Y values. Not yet confirmed with a full-bed-width print — if a print
   looks positioned or clipped oddly, this is the first thing to check.
4. **`M653`/`M656` chamber-related codes** — `S55`/`S300` in a real ABS
   sample, `S0`/`S0` in a real PLA sample; pairs with item 1's `M652` (fan
   off) as a matched ABS-oriented preset. No community documentation found
   for either code. `M653 Sxxx` is fairly likely a chamber heater target in
   °C; `M656 Sxxx`'s leading theory is a chamber pre-heat timeout in seconds
   (`300` = 5 minutes). Neither is hardware-confirmed. Lives in the
   `Generic ABS @FlashForge Creator 4` filament profile.

## Filament profile schema history

For anyone hitting the same issue extending these: three drafts of the
filament profiles were tried before they actually appeared in OrcaSlicer.
First draft guessed `"inherits": "Generic PLA"` and
`bed_temperature`/`first_layer_bed_temperature` — both wrong (the real base
profile name has a `@System` suffix, and bed temp is a set of plate-type
keys, not a single one). Second draft fixed both of those but *still*
didn't appear after a drop-in + restart, so every key from
`fdm_filament_common` + `fdm_filament_pla`/`fdm_filament_abs` got merged
directly into a fully flat `"inherits": ""` file instead. That *still*
didn't fix it. The actual cause: the file was missing
`"filament_extruder_variant": ["Direct Drive Standard"]` — without it,
OrcaSlicer can't confirm the filament is compatible with the printer's
declared extruder variant even when `compatible_printers` matches by name,
and silently filters it out of the list.

**Moral, if you're extending this to a new material**: don't build a
filament profile from scratch or from guessed keys — duplicate one of the
existing files (or do a real "Save As" from inside OrcaSlicer against one of
the profiles here) and edit from there.

## Container format reference

Byte-level `.gx` header layout, gcode dialect findings, and the full manual
OrcaSlicer setup walkthrough this project's presets were originally built
from are preserved in [`../archive/OrcaSlicer_Reproduction_Plan.md`](../archive/OrcaSlicer_Reproduction_Plan.md)
for anyone reproducing this approach for a different Flashforge machine.
