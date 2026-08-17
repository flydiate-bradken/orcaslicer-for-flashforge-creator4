# OrcaSlicer → Flashforge Creator 4 Bridge

Lets you slice for the Flashforge Creator 4 in OrcaSlicer instead of
Flashforge's own FlashPrint 5, by wrapping OrcaSlicer's sliced `.gcode`
output into the proprietary `.gx` container the printer actually expects.

**Scope: right extruder (T0) only.** The Creator 4 is IDEX hardware (two
toolheads), but this bridge deliberately doesn't drive the left head or any
dual-material/mirror/duplicate mode. An experimental, untested dual-extruder
profile set exists separately — see [Dual-extruder](#dual-extruder-both-heads--separate-experimental) below.

There's also a sibling tool for live status, camera, and control over the
network — see [Live status, camera, and control](#live-status-camera-and-control-control) below.

## Status

The core (right-extruder) profiles and post-processing pipeline have been
slice-tested and print-tested on real hardware; one bug found during real
testing is already fixed (see [docs/BACKGROUND.md](docs/BACKGROUND.md)).
Treat your first print on a new setup as supervised regardless — watch the
first layer, and see [Open questions](docs/BACKGROUND.md#open-questions--known-unknowns)
for the handful of specifics that are a documented best guess rather than a
hardware-confirmed fact.

## Prerequisites

- OrcaSlicer (see Install step 1 below). These profiles use format version
  `2.4.0.1` (matching OrcaSlicer 2.4.x) — if your installed version is much
  newer or older, the JSON key set may have drifted; see
  [Troubleshooting](#troubleshooting).
- Python 3.x on your PATH — confirm with:
  ```bash
  python --version
  ```
- Pillow (used to build the two embedded preview images):
  ```bash
  pip install pillow
  ```

## Install

This does **not** touch your existing OrcaSlicer settings automatically —
you copy files into place yourself, so nothing you already have gets
silently overwritten.

1. **Install OrcaSlicer**, if you don't already have it — get it from the
   [Microsoft Store](https://apps.microsoft.com/detail/9MV6GL23XM59) (search
   "OrcaSlicer" if the link doesn't open the Store app directly). This
   installs and updates through Windows like any other Store app, and needs
   no separate download/installer. Launch it once so its `%APPDATA%\OrcaSlicer\`
   settings folder gets created before step 3 below.

2. **Copy the post-processing script to a stable, personal location.**
   Create `%USERPROFILE%\Documents\OrcaFlashforgeCreator4\` and copy the
   entire `post_processing\` folder from this repo into it, so you end up
   with `Documents\OrcaFlashforgeCreator4\post_processing\flashforge_gx_post.py`
   (and `.bat` / `validate_gx.py` alongside it). Keeping it in `Documents`
   rather than wherever you cloned this repo avoids issues with OrcaSlicer
   launching a script from a path with spaces/special characters, and makes
   it trivial to hand off to a coworker.

   The `orcaslicer_profiles\process\*.json` files point at
   `C:\Users\<username>\Documents\OrcaFlashforgeCreator4\post_processing\flashforge_gx_post.bat`
   — **edit the `post_process` value in all 3 process JSON files to use
   your own Windows username** before importing (or fix it afterward in
   OrcaSlicer's Process Settings → Others → Post-processing Scripts).

3. **Copy the profile files into OrcaSlicer's user settings folder:**
   - `orcaslicer_profiles\machine\*.json` → `%APPDATA%\OrcaSlicer\user\default\machine\`
   - `orcaslicer_profiles\process\*.json` → `%APPDATA%\OrcaSlicer\user\default\process\`
   - `orcaslicer_profiles\filament\*.json` → `%APPDATA%\OrcaSlicer\user\default\filament\`

4. **Fully close OrcaSlicer** (check Task Manager, not just the window) if
   it's running, then relaunch it.

5. **Verify the profiles loaded:**
   - Printer dropdown: `FlashForge Creator 4 - 0.4mm Nozzle`, `- 0.6mm
     Nozzle`, and `- 0.8mm Nozzle` all appear.
   - Process dropdown (with one of those printers selected): the matching
     `Standard 0.XXmm @FlashForge Creator 4 ...` profile appears.
   - Filament dropdown: `Generic PLA @FlashForge Creator 4` and `Generic ABS
     @FlashForge Creator 4` appear.
   - **If nothing appears, stop here** and see [Troubleshooting](#troubleshooting).

6. **Test slice.** Load any small test model, pick the printer/process/
   filament triple matching your nozzle and material (see
   [Nozzle variants](#nozzle-variants) below), slice. Open the sliced `.gx`
   file (readable as text past the binary header) and confirm the start
   gcode has real numbers in the `M140 S...` / `M104 S...` lines, not
   literal placeholder text like `[first_layer_bed_temperature]`.

7. **Structural validation** (no printer needed):
   ```bash
   python "%USERPROFILE%\Documents\OrcaFlashforgeCreator4\post_processing\validate_gx.py" "path\to\your\sliced.gx"
   ```
   Confirm it prints `OK: structurally valid` and the header values
   (temperatures, layer height, print speed) look sane.

8. **First real print — supervised.** Copy the `.gx` to USB and print from
   the Creator 4's front panel. Watch the first layer.

## Live status, camera, and control (control/)

Slicing a `.gx` and printing it from USB, above, is one half of what
FlashPrint 5 normally does. The other half — watching the printer live over
the network instead of walking over to the front panel — is a separate,
independent tool in **[control/](control/README.md)**. Neither vanilla
OrcaSlicer nor Flashforge's own OrcaSlicer fork add this for the Creator 4,
so this fills that gap the same way the slicing bridge does.

What it gives you, confirmed working against a real Creator 4 over the
local network: live status/temperature/progress reads, a camera stream, and
control over temperatures and the case lights. (`pause`/`resume`/`stop` are
implemented but not yet confirmed against a real in-progress print — see
its README for details.)

Quickest way in — a local browser dashboard:

```bash
python control/webui/server.py <printer-ip>
```

then open **http://localhost:8000** for live temps, progress, status, and
an embedded camera view. A CLI (`control/ff_control.py`) is also available
for scripting individual commands. Nothing here depends on the slicing
setup above, or vice versa — set up either independently. See
[control/README.md](control/README.md) for full setup, the command
reference, and how to test it without a printer.

## Nozzle variants

Pick the printer + process pair matching the nozzle actually installed on
the printer:

| Nozzle | Printer profile | Process profile | Layer height |
|---|---|---|---|
| 0.4mm | `FlashForge Creator 4 - 0.4mm Nozzle` | `Standard 0.20mm @FlashForge Creator 4 0.4mm Nozzle` | 0.20mm |
| 0.6mm | `FlashForge Creator 4 - 0.6mm Nozzle` | `Standard 0.30mm @FlashForge Creator 4 0.6mm Nozzle` | 0.30mm |
| 0.8mm | `FlashForge Creator 4 - 0.8mm Nozzle` | `Standard 0.40mm @FlashForge Creator 4 0.8mm Nozzle` | 0.40mm |

An extra, faster/coarser process also exists for the 0.6mm nozzle —
`Standard 0.40mm @FlashForge Creator 4 0.6mm Nozzle` (0.4mm layers instead of
the default 0.3mm, still within that nozzle's 0.48mm max). Same printer
profile, just pick this process instead when speed matters more than detail.

See [docs/NOZZLE_VARIANT_TABLE.md](docs/NOZZLE_VARIANT_TABLE.md) for exactly
what's different between them and why.

## Filament profiles

Select the filament profile matching your material (`Generic PLA` or
`Generic ABS @FlashForge Creator 4`) and the material-specific case-fan +
chamber-heat gcode is applied automatically — no manual gcode pasting
needed:

- **PLA**: `M651 S255` (case fan on) / chamber heat off. Nozzle 200°C /
  205°C first layer, bed 55°C.
- **ABS**: `M652` (case fan off) / `M653 S55` / `M656 S300` (chamber heat
  on). Nozzle 230°C / 235°C first layer, bed 110°C.

If you print something other than PLA or ABS, duplicate whichever filament
profile is the closer match (Save As in OrcaSlicer) and adjust
temperatures/gcode as needed — override the case-fan/chamber-heat gcode
values as a matched set, not individually (see
[docs/BACKGROUND.md](docs/BACKGROUND.md) for why).

## Verify it works (no physical printer required)

```bash
python tests\run_structural_test.py
```

Builds a synthetic OrcaSlicer-style gcode fixture, runs it through
`post_processing\flashforge_gx_post.py`, and checks the result with
`post_processing\validate_gx.py` (magic bytes, header field sanity, both
embedded preview images valid, non-empty gcode body). This proves the
pipeline is wired together correctly — it **cannot** prove the output
prints correctly on real hardware, which is what step 8 of Install is for.

To inspect any `.gx` file by hand, including the real reference sample this
bridge was built from:

```bash
python post_processing\validate_gx.py "path\to\file.gx"
python post_processing\validate_gx.py samples\real_creator4_20mm_box.gx
```

## Troubleshooting

**A profile edit doesn't seem to have taken effect, or only part of a file
changed after copying:**
- OrcaSlicer must be fully closed (check Task Manager, not just the window)
  *before* copying updated profile files into place. If it's running with a
  profile loaded, its own background saving can partially overwrite your
  copy. Close it, copy, then relaunch.

**Printer/process/filament profiles don't appear in OrcaSlicer after copying
files + restarting:**
- Confirm you copied into `user\default\machine`, `user\default\process`,
  and `user\default\filament` specifically — not `system\...` or a
  different profile folder.
- Check OrcaSlicer's own log (Help → Show Log File) for JSON parse errors.
- Fallback: open the closest built-in printer/process/filament (e.g.
  "Generic Marlin Printer" at the matching nozzle size, or "Generic
  PLA @System"/"Generic ABS @System"), manually enter the differing fields
  by hand — every value is listed in
  [docs/NOZZLE_VARIANT_TABLE.md](docs/NOZZLE_VARIANT_TABLE.md), the
  "Filament profiles" section above, and the JSON files themselves — then
  Save As with the same name.

**Post-processing step fails / no `.gx` file gets produced:**
- Confirm `python --version` works in a plain terminal.
- Confirm Pillow is installed (`pip show pillow`).
- Confirm the `post_process` path in the process JSON matches where you
  actually put `post_processing\` and uses *your* Windows username — see
  Install step 2.
- Confirm `flashforge_gx_post.bat` and `flashforge_gx_post.py` are still in
  the same folder together — moving just one breaks the other.

**Placeholder text (e.g. `[first_layer_bed_temperature]`) appears literally
in the sliced gcode instead of a number:**
- Means OrcaSlicer didn't recognize that variable name in your installed
  version. Compare against OrcaSlicer's own built-in "Generic Marlin
  Printer" start gcode for the actual supported placeholder syntax in your
  version, and update `machine_start_gcode` accordingly.

**Nozzle temp comes out as 0, or filament usage in the `.gx` header is 0:**
- Usually means OrcaSlicer's footer-comment format differs from what the
  script expects in your version. Open the raw sliced gcode and check for
  lines like `; filament used [mm] =` near the end, and compare against the
  keys listed at the top of `post_processing\flashforge_gx_post.py`.

## Dual-extruder (both heads) — separate, experimental

Everything above drives the right extruder only, and is the proven,
supported path. A separate, **untested** profile set for driving both
Creator 4 extruders (mirror printing / multi-material) lives in
`orcaslicer_profiles_dual_extruder\` — kept fully separate so it can't
affect the proven setup. Read
[docs/DUAL_EXTRUDER_EXPERIMENTAL.md](docs/DUAL_EXTRUDER_EXPERIMENTAL.md)
before touching it — it carries real physical collision risk that nothing
else in this project does, and needs careful supervised testing.

## Repo layout

```
post_processing/
  flashforge_gx_post.py        the converter: gcode -> .gx (source copy -- see Install step 2)
  flashforge_gx_post.bat       Windows launcher wrapper OrcaSlicer actually calls
  validate_gx.py               structural checker for .gx files
orcaslicer_profiles/
  machine/                     3 printer profiles (0.4mm / 0.6mm / 0.8mm nozzle)
  process/                     3 matching process (print settings) profiles, .gx wiring pre-configured
  filament/                    Generic PLA / Generic ABS profiles
orcaslicer_profiles_dual_extruder/   experimental both-heads profile set, see Dual-extruder above
docs/
  NOZZLE_VARIANT_TABLE.md      exactly what differs between the 3 nozzle sizes, and why
  DUAL_EXTRUDER_EXPERIMENTAL.md  read before touching orcaslicer_profiles_dual_extruder/
  BACKGROUND.md                how this was reverse-engineered, confirmed fixes, open questions
samples/                       real FlashPrint 5 reference .gx/.gcode/preview files
tests/                         pipeline test, no OrcaSlicer/printer needed
control/                       live status/camera/start-stop control -- separate tool, see control/README.md
archive/                       historical/superseded/PrusaSlicer-only material, reference only
LICENSE                        GPL-3.0 (flashforge_gx_post.py is a derivative work, see Credits)
```

## Credits / license

`post_processing/flashforge_gx_post.py` is adapted from a prior
Creator-4-specific bridge project, itself a derivative of
[urself25/Orca_Gcode_to_Gx](https://github.com/urself25/Orca_Gcode_to_Gx)
(GPL-3.0), and is distributed under the same license — see `LICENSE`.
