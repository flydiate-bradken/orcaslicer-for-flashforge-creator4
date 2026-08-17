# Dual-extruder (both Creator 4 heads) — EXPERIMENTAL, untested on hardware

Everything else in this project (`orcaslicer_profiles/`) drives the Creator 4's
**right extruder only**, and every gcode decision in it was confirmed against
a real, working FlashPrint 5 export before being trusted. This document, and
the separate `orcaslicer_profiles_dual_extruder/` profile set it describes,
is different: it's built from a **single** real dual-extruder FlashPrint
sample, and has **not yet been print-tested** — treat it as a first draft to
verify carefully, not a proven bridge.

**Why this is a separate profile set, not an extension of the main one**: the
single-extruder profiles are proven working (real successful print, see
README.md "Confirmed fixes from real hardware testing"). This dual-extruder
work is intentionally kept in its own folder so nothing here can accidentally
affect that working setup, and so it's obvious which files are which — every
name in this set ends in `(EXPERIMENTAL)`.

## The reference sample: `IDEX_Print.gx`

A real FlashPrint 5 export, both extruders loaded with PLA, a mirror-mode
print (both heads print similar/mirrored geometry every layer — not a
"different material per feature" single-object print). 111 tool-change
commands across 55 layers, `multi_extruder_type = 3` in the header (vs `5`
for the right-only samples this project is otherwise built from) — confirming
that field really does reflect which extruders are active, not something
fixed.

## Confirmed findings (from directly inspecting the real gcode)

1. **`M118` declares both active tools**: `M118 X30.00 Y30.00 Z10.10 T0 T1`
   (vs. just `T0` in the single-extruder samples).
2. **Both extruders get real temps and waits**: `M104 S200 T0` and
   `M104 S200 T1`; `M900 K0.000 T0` and `M900 K0.000 T1`; `M6 T0` and `M6 T1`
   (both waited on, vs. the single-extruder profile's `M104 S0 T1` to keep
   the left head off entirely).
3. **No extruder-offset compensation gcode anywhere** — searched the whole
   file for `G92 X`/`G92 Y`, `M206`, `M218`: none found. The firmware
   translates gcode coordinates to the correct physical carriage position
   internally based on which tool (`T0`/`T1`) is currently active via
   `M108 Tn`. This is the single biggest de-risking finding — it means the
   machine profile does **not** need manual offset math, just
   `extruder_offset: ["0x0", "0x0"]` for both.
4. **Each active tool maintains its own independent absolute E position.**
   Confirmed directly: after several hundred lines of `T1` extruding at its
   own climbing E values, switching back to `T0` resumes at *exactly* the E
   value `T0` was last left at, unrelated to what `T1`'s counter was doing in
   between. `E` means "whichever tool is currently active's position."
   OrcaSlicer's own multi-extruder toolchange logic is expected to track this
   the same way for a properly-declared multi-extruder printer — this hasn't
   been separately confirmed, but is standard behavior for this class of
   slicer profile.
5. **~1.0mm retract immediately before each `M108` tool-change** — matches
   this project's existing `retract_length_toolchange: ["1"]` value exactly
   (inherited from the original reference file this whole project started
   from, and apparently correctly calibrated).
6. **Z only increments once per layer cycle**, not once per tool-switch —
   whichever tool resumes "first" in a given layer does the `G1 Z...` move;
   the other tool's resume doesn't repeat it.
7. **End gcode needs `M104 S0` for both `T0` and `T1`** (the single-extruder
   end gcode only needed `T0`, since `T1` was never turned on to begin with).

## What the new profile does with this

`orcaslicer_profiles_dual_extruder/machine/FlashForge Creator 4 - Dual 0.4mm
(EXPERIMENTAL).json` — built from the proven single-extruder 0.4mm profile,
with per-extruder-physical settings (`nozzle_diameter`, `extruder_offset`,
retraction settings, etc.) duplicated to 2-entry arrays, one per tool.
`machine_start_gcode`/`machine_end_gcode` are parameterized with OrcaSlicer's
own per-extruder-indexed template syntax — confirmed real, taken directly
from OrcaSlicer's own `fdm_toolchanger_common.json`
(`{if is_extruder_used[1]}...{endif}`, `{first_layer_temperature[1]}`) — so
the *same* profile gracefully handles a single-extruder print (behaves like
the proven profile, `M104 S0 T1`) or a genuine dual-extruder print (real T1
temp, real T1 wait), rather than needing two different profiles for that
distinction.

```
M118 X200 Y175 Z500 T0{if is_extruder_used[1]} T1{endif}
M140 S[first_layer_bed_temperature] T0
M104 S{first_layer_temperature[0]} T0
{if is_extruder_used[1]}M104 S{first_layer_temperature[1]} T1{else}M104 S0 T1{endif}
M654 P60
M653 S0
M656 S0
M107 T0
M107 T1
M204 S1000
M900 K0.000 T0
{if is_extruder_used[1]}M900 K0.000 T1{endif}
G90
G1 Z50.000 F420
M7 T0
M6 T0
{if is_extruder_used[1]}M6 T1{endif}
M652
M108 T[initial_tool]
```

## Wipe tower is disabled, and can't be re-enabled without breaking extrusion

OrcaSlicer's Wipe/Prime Tower feature (`enable_prime_tower`) refuses to slice
with an error — **"The Wipe Tower is currently only supported with the
relative extruder addressing (use_relative_e_distances=1)"** — unless
relative E is on. But relative E is confirmed, via a real failed print, to
break extrusion entirely on this hardware (see README.md "Confirmed fixes
from real hardware testing" — that's the whole reason
`use_relative_e_distances=0` exists in the first place). These two
requirements are mutually exclusive on this printer as currently understood.

**Fix applied**: `enable_prime_tower` set to `0` in the dual-extruder process
profile. This isn't a workaround so much as matching reality — the real
`IDEX_Print.gx` reference never used a wipe tower either, just a direct
retract-and-resume at each `M108` tool change with no separate purge
structure. **Do not re-enable the wipe tower on this printer** without first
re-confirming `use_relative_e_distances=0` still works — if OrcaSlicer's UI
lets you turn prime tower back on, it will likely silently flip
`use_relative_e_distances` back to `1` to permit it, which would reproduce
the "extruder didn't work" failure from earlier testing.

**Consequence**: without a wipe tower, be aware that OrcaSlicer's own
purge/color-cleanliness logic for tool changes is not being used — whatever
minimal retract-and-resume the printer profile's own settings produce
(matching the real sample) is all the "purge" that happens. For two
same-material objects (as in the actual test that surfaced this error) that
shouldn't matter; for genuinely different materials on adjacent
prints/features, expect more cross-contamination/oozing at transitions than
a wipe-tower-equipped setup would have.

## What's NOT confirmed — read this before testing

- **`change_filament_gcode: "M108 T{next_extruder}"`** — the `{next_extruder}`
  placeholder is standard PrusaSlicer/OrcaSlicer convention, but there is no
  real marlin-flavor multi-extruder Creator 4 sample to confirm it against
  (OrcaSlicer's own toolchanger reference uses Klipper flavor with a
  completely different, much more elaborate purge-based toolchange sequence
  that doesn't match this printer's hardware at all — not reusable here).
  **Before any physical print**: slice a small test model and check the
  gcode preview shows real `M108 T0`/`M108 T1` lines at tool-change points,
  not literal unsubstituted `{next_extruder}` text.
- **`printer_extruder_id`, `physical_extruder_map`, `printer_extruder_variant`**
  were left as single-value (matching the proven profile) rather than
  duplicated to 2 entries — no real reference confirmed whether these need to
  become arrays for a true 2-physical-extruder machine. If OrcaSlicer's UI
  doesn't correctly recognize this as a 2-extruder printer after import
  (check: does the Filament panel show 2 extruder slots?), this is the first
  thing to investigate.
- **Whose filament gcode "wins" for material-specific behavior** (the
  `M651`/`M652`/`M653`/`M656` case-fan/chamber-heat commands that live in the
  filament profiles) when T0 and T1 have *different* filaments assigned —
  genuinely untested. The two filament profiles in this set
  (`Generic PLA/ABS @FlashForge Creator 4 Dual (EXPERIMENTAL)`) are direct
  copies of the proven single-extruder ones, unchanged — fine if both
  extruders use the same material (as the real reference sample did), but if
  you assign different materials to each tool, watch closely for which
  filament's start gcode actually executes.
- **The reference sample was mirror-mode**, not a true single-object
  multi-material print (different regions/features in different materials).
  The tool-switching mechanism this profile is built on should be identical
  either way, but that's an inference, not something separately confirmed —
  OrcaSlicer's own UI feature for driving *which* mode gets used (mirror
  print vs. per-object/per-part extruder assignment) hasn't been explored
  yet either.
- **Bed origin, and the handful of items already flagged as open questions
  in the main README** (trailing `.gx` header byte, `M656`'s exact meaning,
  etc.) apply here too, unchanged.

## How to test safely

1. **Don't print anything yet.** First: copy the 3 files in
   `orcaslicer_profiles_dual_extruder/` into OrcaSlicer's user folders the
   same way as the main project (machine → `user\default\machine`, process →
   `user\default\process`, filament → `user\default\filament`), with
   OrcaSlicer fully closed first.
2. Relaunch, select the `(EXPERIMENTAL)` printer/process, assign both
   extruders in the OrcaSlicer UI (however it exposes that — check the
   Filament panel for 2 extruder slots first), slice a small test object.
3. **Read the actual gcode output before anything else** — confirm:
   - No unsubstituted `{...}` template text anywhere (would mean a
     placeholder name is wrong)
   - `M118 ... T0 T1` line has real coordinates
   - Both `M104`/`M900`/`M6` pairs appear with real temps for both tools
   - `M108 T0`/`M108 T1` alternate sensibly at tool-change points
   - End gcode turns off both `T0` and `T1`
4. **First physical test should be closely supervised the entire time**,
   watching specifically for the two failure modes single-extruder testing
   never risked: the idle head colliding with the print or the active head,
   and incorrect tool-change behavior (wrong head extruding, or neither).
   Be ready to hit the physical stop/pause button.
5. Send me the sliced `.gx` before printing it, same as every other test in
   this project — I can check the gcode structure the same way I did for
   `IDEX_Print.gx`, before you commit any filament or hardware risk to it.
