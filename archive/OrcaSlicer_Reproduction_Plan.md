# Reproducing the OrcaSlicer → Flashforge Creator 4 Bridge

**Scope**: this document covers the OrcaSlicer path only. A parallel PrusaSlicer
setup exists in the same project but isn't covered here.

**Status as of writing**: the full pipeline (OrcaSlicer → confirmed printer
profile → post-processing script → `.gx` file) has been slice-tested and
produces a structurally valid file, confirmed against a real Flashforge
export. It has **not yet been print-tested on physical hardware** — treat a
first print as supervised, not unattended.

**Companion files required** (must travel with this document, referenced by
name throughout):
```
scripts/flashforge_gx_post.py    the post-processing script itself
scripts/flashforge_gx_post.bat   Windows launcher wrapper (required, see Phase 4)
scripts/validate_gx.py           structural validator for .gx output
samples/real_creator4_20mm_box.gx      real FlashPrint 5 reference export
samples/real_creator4_20mm_box.gcode   its gcode body, extracted
```

---

## 1. Background: why this exists

The Flashforge Creator 4 (an IDEX FFF printer) doesn't accept plain `.gcode`.
Flashforge's own slicer, FlashPrint 5, wraps sliced output in a proprietary
binary container (`.gx`) and the firmware expects a handful of Flashforge-
specific gcode commands in the body. There is no first-party OrcaSlicer
support for this machine (Flashforge's own OrcaSlicer fork covers the
Adventurer 5M family, AD5X, Guider 3 Ultra, and Creator 5 — not Creator 4).

This project builds a bridge: a post-processing script that wraps OrcaSlicer's
sliced output into the correct `.gx` format, paired with an OrcaSlicer printer
setup that emits the correct Flashforge-specific start/end gcode. Everything
below was derived from a **real FlashPrint 5 export** for the Creator 4 (a
20mm calibration cube, right extruder only, ABS) rather than guessed —
byte-level analysis of that file is what the confirmed values in this
document come from.

**Deliberate scope limit**: right extruder (T0) only. The Creator 4 is IDEX
hardware with a second (left) extruder and dual-material/mirror/duplicate
modes; none of that is addressed here.

---

## 2. Prerequisites

- OrcaSlicer installed (developed/tested against **2.4.2**; menu names may
  differ slightly in other versions)
- Python 3 with Pillow installed (`pip install pillow`)
- A real `.gx` file exported from FlashPrint 5 for the target printer, if
  reproducing this methodology for a *different* Flashforge machine or
  firmware version than the one already confirmed here (see Phase 1)
- Physical access to the printer for the final supervised test print

---

## 3. Phase 1 — Establish ground truth from a real FlashPrint export

**This is the foundation everything else depends on.** Do not skip it or
substitute assumptions from a different Flashforge model — the container
format and gcode dialect vary between machines (confirmed: differs from both
the Adventurer 4 and the Creator Pro 2 in specific, non-obvious ways — see
Phase 2 and Phase 3).

1. In FlashPrint 5, slice a small, simple object (a calibration cube is
   ideal) for the target printer, right extruder only, using a default
   material profile. Export/save the resulting file.
2. Note the file extension — for the Creator 4 this is `.gx` (binary). Other
   Flashforge machines may use a different variant.
3. Keep this file — it's the reference everything is checked against.

---

## 4. Phase 2 — Reverse-engineer the container format

Open the real `.gx` file in a hex editor or a small Python script using
`struct`. What was found for the Creator 4 (confirmed via
`samples/real_creator4_20mm_box.gx`):

**Fixed header, 58 bytes total, all integers little-endian:**

| Offset | Field | Type | Notes |
|---|---|---|---|
| 0x00 | Magic | 12 bytes | literal `"xgcode 1.0\n\0"` |
| 0x0C | reserved | int32 | observed `0` |
| 0x10 | `bmp_offset` | int32 | observed `58` (= end of fixed header) |
| 0x14 | `png_offset` | int32 | offset where a **second** embedded image starts |
| 0x18 | `gcode_offset` | int32 | offset where the gcode text body starts |
| 0x1C | `print_time` | int32 | seconds |
| 0x20 | `filament_used_right_mm` | int32 | |
| 0x24 | `filament_used_left_mm` | int32 | `0` for right-only prints |
| 0x28 | `multi_extruder_type` | int16 | **`5`** for right-only on this IDEX machine (not `0` — that's what a genuinely single-extruder Flashforge machine like the Adventurer 4 uses) |
| 0x2A | `layer_height_um` | int16 | |
| 0x2C | reserved | int16 | observed `0` |
| 0x2E | "mode" field | int16 | **`3`** — meaning unknown, reproduced as observed |
| 0x30 | `print_speed` | int16 | mm/s |
| 0x32 | `bed_temp` | int16 | °C |
| 0x34 | `nozzle_temp` | int16 | °C |
| 0x36 | `nozzle_temp` (duplicate) | int16 | same value repeated |
| 0x38 | reserved | int16 | observed `0` |

**Followed by, back to back:**
1. An **80×60 BMP** (list-view icon) starting at `bmp_offset`
2. A **320×320 PNG** (detail-view render) starting at `png_offset` — this was
   the biggest surprise: the reference implementation this was adapted from
   (built for the Adventurer 4) only embeds one BMP. Missing the second image
   would shift every offset after it and likely break the firmware's parsing.
3. The gcode text body, starting at `gcode_offset`

**Method to verify this on a different sample**: find the BMP magic (`BM`,
`0x42 0x4D`) right after the fixed header; the 4-byte little-endian integer
immediately after that magic is the BMP's declared size — `bmp_offset + that
size` should land exactly on `png_offset`. Similarly, search for the PNG
magic (`\x89PNG\r\n\x1a\n`) at `png_offset`, then find its `IEND` chunk to
get the PNG's true end, which should equal `gcode_offset`. `scripts/
validate_gx.py` implements exactly this check — run it against any `.gx`
file to sanity-check a header this way.

---

## 5. Phase 3 — Reverse-engineer the firmware's gcode dialect

Extract the gcode text body (everything after `gcode_offset`) and read the
start and end sections by hand.

**Confirmed real start gcode** (right extruder, ABS, from the reference
sample):
```gcode
M118 X16.63 Y16.63 Z21.22 T0
M140 S110 T0
M104 S235 T0
M104 S0 T1
M654 P60
M653 S55
M656 S300
M107 T0
M107 T1
M204 S1000
M900 K0.000 T0
G90
G1 Z50.000 F420
M7 T0
M6 T0
M652
M108 T0
```

**Confirmed real end gcode:**
```gcode
M104 S0 T0
M140 S0 T0
G162 Z F1800
M652
G91
M18
```

**Notable findings, all confirmed by direct inspection (no `G28`, `G161`, or
`M132` appear anywhere in the entire file — searched exhaustively):**
- **No homing commands at all.** This machine apparently doesn't home via
  the print gcode itself — likely because the Creator 4 has auto bed
  leveling and the touchscreen's own "start print" routine handles homing/
  leveling before it even begins executing the file (this part is inference,
  reasonably well supported by Flashforge's own marketing of the Creator 4
  having auto leveling, and by Flashforge's wiki for the architecturally
  similar Creator 5 explicitly documenting a pre-print homing/leveling/
  heating routine — but not confirmed by a Creator-4-specific primary
  source). **Verify this by watching the very first ~30 seconds of the
  first real print** — if the printer doesn't visibly home/probe on its own
  before moving into the gcode's motion, the `G1 Z50.000 F420` line early
  in the start gcode could crash into the bed or frame.
- `M108 Tn` is the tool-selection convention (not bare `Tn`) — matches
  documented Flashforge gcode conventions broadly, not specific to Creator 4.
- `M654`/`M653`/`M656`/`M652` are Flashforge-specific M-codes with **no
  documented meaning found anywhere** — reproduced with their exact observed
  parameter values rather than guessed at.
- Coordinates in the body are centered near `(0,0)`, not corner-origin —
  confirmed from the sample's X/Y values ranging roughly ±16mm for a 20mm
  part. The full bed extent was not directly observed (the test part was
  small and centered), so the bed shape used downstream (`-200,-175` to
  `200,175`, based on the published 400×350mm build volume) is an inference,
  not a direct confirmation of the exact usable range or origin offset.
- Config-dump comments at the end of the real file confirm the exact working
  combination: ABS, 0.18mm layers, 3 perimeters/walls, 4 top / 3 bottom
  shells, 20% hexagon infill, 50mm/s print speed, 80mm/s travel, 235°C
  first-layer nozzle / 230°C nozzle, 110°C bed.

If reproducing this for a different Flashforge machine, repeat this
extraction and comparison — do not assume the same M-codes or absence of
homing carries over; it did not carry over from the Creator Pro 2 (which
*does* use `G161`/`M132` in its own PrusaSlicer community profile).

---

## 6. Phase 4 — Build the post-processing script

The script (`scripts/flashforge_gx_post.py`) is adapted from
[`urself25/Orca_Gcode_to_Gx`](https://github.com/urself25/Orca_Gcode_to_Gx)
(GPL-3.0), a reference implementation built for the Flashforge Adventurer 4.
Key adaptations made for the Creator 4:

1. **Two embedded images, not one** — generates an 80×60 BMP and a 320×320
   PNG from the slicer's own embedded gcode-viewer thumbnail (letterboxed
   onto a black square for the PNG to preserve aspect ratio without
   distortion — it's not a true 3D render like FlashPrint's own preview).
2. **Dynamic offsets, not hardcoded ones** — the reference implementation
   assumed a fixed-size thumbnail and hardcoded the header's offset fields;
   this version computes them from the actual generated image sizes, which
   is necessary once a second, variable-size image is in the mix.
3. **`multi_extruder_type = 5`** and header mode field `= 3`, matching the
   Phase 2 findings (the reference implementation forces `0`, correct only
   for genuinely single-extruder machines).
4. **Nozzle-temperature comment key**: checks both `; temperature =`
   (PrusaSlicer) and `; nozzle_temperature =` (OrcaSlicer) — the reference
   implementation only checked the OrcaSlicer spelling. All other metadata
   comment keys (print time, filament used, layer height, bed temp,
   thumbnail block delimiters) were confirmed identical between the two
   slicers.
5. **No `T0`/`T1` injection** — the original reference script injects a bare
   `T0` command into the gcode body via a fragile comment-marker search.
   Removed: Flashforge firmware doesn't recognize bare `Tn` (confirmed —
   the real sample never uses it, only `M108 Tn`), and tool selection is
   handled correctly by the machine start gcode instead (Phase 5).

Wire-up contract (same for both slicers): the script is invoked with the
sliced gcode file's path as its last CLI argument, and must read gcode from
and overwrite that same file in place.

---

## 7. Phase 5 — Set up OrcaSlicer (manual UI method — confirmed working)

**Two automated import approaches were tried and both failed** — this
section explains why, so the manual route isn't mistaken for the easy path
being skipped unnecessarily:

- A PrusaSlicer-style `.ini` config bundle: OrcaSlicer's Import dialog
  simply doesn't accept `.ini` — confirmed directly from the file picker
  (only `.json`, `.zip`, `.orca_printer`, `.orca_bundle`, `.orca_filament`
  are offered).
- Native OrcaSlicer `.json` presets, built to mirror OrcaSlicer's own
  *source-tree* profile format (thin files with an `"inherits"` chain
  pointing at internal base profiles): importing these produced **"There
  are 0 configs imported"**, including the printer profile itself. This
  matches a known, long-open OrcaSlicer bug
  ([issue #4944](https://github.com/OrcaSlicer/OrcaSlicer/issues/4944),
  closed as "not planned") affecting many unrelated printers/versions,
  including configs exported from OrcaSlicer itself — Import Configs
  appears to be broadly unreliable, not specific to these files.

**The manual UI method, confirmed working end-to-end by live testing:**

### 5a. Add the printer

1. Printer preset dropdown → **Add printer**.
2. Vendor **"Custom"** → **"MyMarlin"** / "Generic Marlin Printer" 0.4mm
   nozzle as the starting base (a real template OrcaSlicer ships
   specifically for unlisted Marlin-flavor printers).
3. Open its settings and **Save As**: `Flashforge Creator 4 (Right
   Extruder)`.

### 5b. Physical printer settings

- **Nozzle diameter**: `0.4`
- **Bed shape**: rectangular, Size `400 x 350`, Origin `-200, -175` (centers
  the bed on 0,0 — see Phase 3's coordinate-system finding). If your Orca
  version wants explicit corner points instead: `-200,-175`, `200,-175`,
  `200,175`, `-200,175`.
- **Max print height**: `500`
- **G-code flavor**: `Marlin`

### 5c. Machine G-code

Open **Machine G-code** and replace **Machine start G-code** / **Machine
end G-code** with the blocks below. **Placeholder syntax note — confirmed by
live testing, not documentation**: `M118`'s bounding-box values were
originally templated with PrusaSlicer-style variable names
(`{first_layer_print_max[0]}`, `{max_layer_z}`); OrcaSlicer's parser rejected
those outright with `Parsing error: Not a variable name`. Since `M118` is
purely informational (declares a bounding box, doesn't affect actual print
geometry), it's hardcoded below to the full bed footprint/height instead of
risking another unverified variable name. The temperature placeholders
(`[first_layer_bed_temperature]`, `[first_layer_temperature]`) **are**
confirmed correct — they're exactly what OrcaSlicer's own "Generic Marlin
Printer" template auto-fills for the equivalent lines, and were verified
by inspecting real exported gcode showing substituted numbers.

**Machine start G-code:**
```gcode
M118 X200 Y175 Z500 T0
M140 S[first_layer_bed_temperature] T0
M104 S[first_layer_temperature] T0
M104 S0 T1
M654 P60
M653 S55
M656 S300
M107 T0
M107 T1
M204 S1000
M900 K0.000 T0
G90
G1 Z50.000 F420
M7 T0
M6 T0
M652
M108 T0
```

**Machine end G-code:**
```gcode
M107 T0
M107 T1
M104 S0 T0
M140 S0 T0
G162 Z F1800
M652
G91
M18
```

### 5d. Filament (confirmed-working ABS)

1. Select built-in **Generic ABS** → edit → **Temperature**:
   - Nozzle, initial layer: `235`; other layers: `230`
   - Bed temperature: OrcaSlicer sets this **per plate type** (Cool/
     Engineering/Hot/Textured PEI, etc.) — set **all** of them to `110` so
     it's correct regardless of which plate type ends up selected.
2. **Save As**: `Generic ABS @Flashforge Creator 4`.

(A PLA variant can be built the same way with 210°C/205°C nozzle and 60°C
bed — these values are a reasonable default, not confirmed against real
hardware output the way the ABS ones are.)

### 5e. Process (confirmed-working 0.18mm)

Base on **0.20mm Standard**, then set: layer height `0.18` (both layer and
first-layer height), wall loops `3`, top shell layers `4`, bottom shell
layers `3`, sparse infill density `20%` / pattern `Hexagon`, outer+inner
wall speed `50`, sparse infill speed `50`, travel speed `80`, initial layer
speed `50`. **Save As**: `0.18mm CONFIRMED (FlashPrint defaults) @Flashforge
Creator 4`.

---

## 8. Phase 6 — Wire up the post-processing script (Windows-specific gotchas)

Three separate failures were hit and fixed here, in order — all confirmed
via live testing, worth reproducing exactly to avoid repeating them:

1. **Post-processing Scripts field must point at a directly-executable
   file, not the `.py` itself.** Pointing it at `flashforge_gx_post.py`
   fails with `Win32 error: 193` / `ERROR_BAD_EXE_FORMAT` — OrcaSlicer
   launches whatever path you give it as a program in its own right, and a
   `.py` file isn't a valid Windows executable. Fix: point it at
   `flashforge_gx_post.bat` instead — a one-line wrapper
   (`python "%~dp0flashforge_gx_post.py" %*`) that Windows *can* launch
   directly, which calls Python internally.
2. **The `.bat` and `.py` files must be in the same folder as each other.**
   The wrapper finds its `.py` via `%~dp0` ("the folder this `.bat` is
   in"). Moving/copying only the `.bat` elsewhere fails with `Error code:
   2` (Python's own exit code for "script file not found"). They can live
   anywhere as long as they travel together.
3. **Use the full absolute path in the field, not a bare filename.** A bare
   filename resolved relative to OrcaSlicer's own config folder
   (`%APPDATA%\OrcaSlicer\`) rather than the intended location. If your
   Orca version has a Browse (`...`) button next to the field, use it
   instead of typing/pasting, to avoid this entirely.

Concretely:
1. **Process Settings → Others → Post-processing Scripts**: full absolute
   path to `flashforge_gx_post.bat`, quoted if it contains spaces, e.g.
   `"C:\path\to\flashforge_gx_post.bat"`.
2. **Output filename format**: change the extension to `.gx`, e.g.
   `{input_filename_base}.gx`.

---

## 9. Phase 7 — Validate and test

1. **Structural validation** (no printer needed): run
   `python scripts/validate_gx.py <file.gx>` on any produced file. It checks
   magic bytes, header field sanity, both embedded images' validity and
   offset consistency, and that the gcode body looks like gcode. Run it
   against `samples/real_creator4_20mm_box.gx` too — a correct
   implementation should report the same structural shape (though different
   values) for both.
2. **Placeholder-substitution check**: after slicing, open the exported
   gcode and confirm the `M140 S...` / `M104 S...` lines show real numbers,
   not literal unsubstituted `[...]`/`{...}` text, and that those numbers
   match what was actually set.
3. **Real print test**: copy the resulting `.gx` to a USB drive and print
   from the Creator 4's front panel — **supervised**, watching closely for
   the first ~30 seconds specifically to confirm homing/leveling behavior
   (see Phase 3's open question) before walking away.

---

## 10. Open questions / known unknowns

Carry these forward if reproducing or extending this work:

1. Whether the Creator 4 truly auto-homes/levels via its own touchscreen
   print-start routine, independent of gcode content (see Phase 3) —
   inferred, not confirmed by a primary source for this exact model.
2. The full usable bed extent and exact coordinate origin (only confirmed
   "centered," not the precise range or whether it's offset for the right
   IDEX head specifically).
3. The real meaning of `M654`, `M653`, `M656`, `M652`, and `M118` —
   reproduced with observed-working literal values; nobody currently knows
   what they actually do.
4. PLA (or any non-ABS material) temps/settings are a best-effort guess,
   not confirmed against real hardware output the way ABS is.
5. A full print (not just a slice) using the OrcaSlicer path specifically
   has not yet been completed — the `.gx` container and gcode sequence are
   confirmed structurally and byte-for-byte against a real FlashPrint
   export, but an actual OrcaSlicer-driven print's success on hardware is
   still pending confirmation as of this document.
