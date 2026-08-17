# PrusaSlicer → Flashforge Creator 4 translation layer

> **Historical snapshot.** This is the plan as approved before implementation
> started, kept here as a record. It predates the real Creator 4 sample
> (findings from that superseded several assumptions here — see README.md's
> "Confirmed from a real sample") and the OrcaSlicer profile added afterward.
> For current status and setup, see [README.md](README.md),
> [README-PrusaSlicer.md](README-PrusaSlicer.md), and
> [README-OrcaSlicer.md](README-OrcaSlicer.md) instead.

## Context

The Creator 4 (an IDEX FFF printer) only accepts print jobs produced by Flashforge's own FlashPrint 5, because Flashforge printers don't consume plain `.gcode`. The goal is to let PrusaSlicer (chosen over OrcaSlicer for this first pass) drive the Creator 4 instead, using only the single right extruder (T0) for now, with output delivered as a file placed on a USB stick as a proof of concept (the normal workflow is network transfer, but that's out of scope for v1).

Research (see below) shows this isn't just "a few odd M-codes" — Flashforge wraps the gcode in a proprietary binary container (`.gx`), and the firmware also expects Flashforge-specific command sequences in the body itself. Both parts are needed for a working translation layer.

## What research found

- **Container format**: Flashforge's `.gx` file is: a magic header `"xgcode 1.0\n\0"`, then a binary metadata block (print time, filament usage, layer height, bed/nozzle temps, a "multi-extruder type" flag, offsets to the thumbnail and gcode sections), then an embedded BMP preview thumbnail (shown on the printer's screen), then the gcode body itself. Two independent sources (a GPL-licensed converter project and an independent reverse-engineering write-up) agree closely on this layout, giving us cross-checked ground truth to build from.
- **Body-level differences**: Flashforge firmware expects its own conventions in the gcode body — e.g. `M108 Tn` rather than bare `Tn` for tool selection, `M132` to load extruder offsets from EEPROM, `G161`/`G162` for homing/platform moves, `M6`/`M7` temperature-wait — seen consistently across Flashforge IDEX machines (Creator Pro 2, Adventurer 4). These belong in PrusaSlicer's **Custom G-code** fields, not the post-processor.
- **A working reference implementation exists**: [`urself25/Orca_Gcode_to_Gx`](https://github.com/urself25/Orca_Gcode_to_Gx) (GPL-3.0) is a Python script, tested against a real Flashforge Adventurer 4, that does exactly this translation for OrcaSlicer output — read the sliced file, pull print-time/filament/temp/layer-height out of the slicer's own comments, pull the embedded thumbnail PNG out of the `thumbnail begin/end` base64 block and convert it to BMP, pack the binary header with `struct`, and concatenate header+thumbnail+gcode. It ships both single-extruder and dual-extruder variants and is wired in as a **PrusaSlicer/OrcaSlicer post-processing script** — a documented extension point where the slicer calls the script with the sliced file's path as its last argument, and the script reads/rewrites that file in place. This is the same mechanism we'll use.
- **OrcaSlicer's gcode comments are a close cousin of PrusaSlicer's** (Orca is a Prusa fork) but not guaranteed identical — the exact comment strings the reference script matches on (`; filament used [mm] =`, `; estimated printing time...`, thumbnail delimiters) need to be confirmed against real PrusaSlicer output rather than assumed.
- **Confirms the premise**: Flashforge's own newer OrcaSlicer fork ("Orca-Flashforge" / "Flash Studio") officially supports the Adventurer 5M family, AD5X, Guider 3 Ultra, and Creator 5 — but explicitly *not* Creator 4. There's no first-party bridge for this machine.
- **Open question we can't resolve from docs alone**: whether the Creator 4 specifically wants `.gx` (binary+thumbnail) or the simpler `.g` variant, the exact header field values it expects, and its exact start/end gcode sequence (IDEX firmware may still emit init commands for the unused left head even in single-extruder mode). The only reliable way to pin this down is a real sample.

## Plan

### Phase 0 — New project folder
Create a new project folder at `C:\Users\flydiate\OneDrive - bradken.com\Documents\Bradken\CurrentWork\M&T_R&D\ClaudeTools\FlashforgeCreator4Bridge\` (sibling to the ProbeWearVisulisationTool folder this session started in) to hold everything below — it's unrelated to that project and shouldn't live inside it.

### Phase 1 — Ground truth from a real sample
You'll slice a small calibration cube in FlashPrint 5 for the Creator 4 (right extruder, PLA, default settings) and share the resulting file. We inspect it (hex/struct dump) to confirm:
- File extension/magic bytes (`.gx` binary vs plain `.g`/`.gcode`)
- Exact header field layout and values (cross-checked against the two documented layouts above)
- Exact start gcode (homing, bed leveling, extruder-offset load, heat-up order) and end gcode (park, motors off, any chamber/fan handling) — including any left-extruder init commands present even in single-head prints

In parallel, we slice the same cube in a new PrusaSlicer "Creator 4" printer profile (bed 400×350×500 mm, single right nozzle) to get a baseline plain-gcode sample to diff against.

### Phase 2 — PrusaSlicer printer profile
New PrusaSlicer printer preset for the Creator 4:
- Bed shape/size, single right extruder, appropriate nozzle/filament defaults
- **Custom Start G-code / End G-code** fields populated with the Flashforge-specific sequence identified in Phase 1 (adapted from the Creator Pro 2 community profile as a starting template, corrected against the real Creator 4 sample)
- Output filename format tweaked so the post-processed file lands with the right extension (the reference project does this via `gcode`→`gx` in the filename-format field)

### Phase 3 — Post-processing script (`flashforge_gx_post.py`)
Standalone Python script (stdlib + Pillow, same deps as the reference project), invoked by PrusaSlicer as a post-processing script (reads the file path from its last CLI arg, per PrusaSlicer's documented contract):
- Parse print time, filament length, layer height, bed/nozzle temps from PrusaSlicer's own comments (regexes confirmed against Phase 1's real Prusa output)
- Extract PrusaSlicer's embedded thumbnail PNG from the `thumbnail begin/end` block, convert to the size/format Creator 4 expects
- Pack the binary header (`struct`) using the offsets/values confirmed in Phase 1, forcing single/right-extruder metadata
- Concatenate header + thumbnail + gcode body, write out in place
- Built and licensed compatibly with the GPL-3.0 reference project we're adapting from (attribute it; keep it GPL if we lift substantial logic)

Adapted from `Orca_Gcode_to_Gx.py`'s single-extruder variant as the starting point rather than written from scratch, since it's a tested, working implementation of the same container format.

### Phase 4 — End-to-end test
- Slice the calibration cube through the new PrusaSlicer profile, run the post-processor, and structurally validate the output (magic bytes, header field values, valid BMP, non-empty gcode body) with a small check script
- You physically print the result on the Creator 4 from a USB stick and confirm it prints correctly (dimensions, no errors, correct thumbnail on screen) — this step needs you, since I can't drive the hardware
- Iterate on Phase 2/3 based on what actually happens on the printer

The `FlashforgeCreator4Bridge` folder from Phase 0 will end up containing: the PrusaSlicer config bundle (`.ini`/preset), `flashforge_gx_post.py`, a small validation/inspection script, and a short README covering setup (installing the profile, pointing PrusaSlicer's post-processing script field at the Python script) and how to re-run the sample test.

## Verification
1. Structural: a small Python check script asserts the produced file's magic bytes, header field values, embedded BMP validity, and gcode body integrity — run automatically after each slice.
2. Real-world: you print the calibration cube (and later a more complex model) on the Creator 4 from USB and confirm correct output — reported back so we can fix anything the structural check can't catch (e.g. wrong start-gcode homing sequence).
