# PrusaSlicer setup — Flashforge Creator 4 Bridge

See [README.md](README.md) for shared background (why this exists, what's
been confirmed from a real Creator 4 sample, how the `.gx` format works).
This page is just the PrusaSlicer-specific setup steps and caveats.

## Setup

1. In PrusaSlicer: **File → Import Config Bundle...** → select
   `profile/FlashforgeCreator4_PrusaSlicer.ini`.
2. Select the **"Flashforge Creator 4 (Right Extruder)"** printer profile,
   the **"0.18mm CONFIRMED (FlashPrint defaults)"** print profile, and the
   **"Generic ABS"** filament profile (the combination actually confirmed
   against real hardware output — swap to PLA/other settings at your own
   risk until that's been tested too).
3. In **Print Settings → Output options**:
   - **Post-processing scripts**: point it at **`scripts/flashforge_gx_post.bat`**
     (Windows), e.g. `C:\path\to\FlashforgeCreator4Bridge\scripts\flashforge_gx_post.bat`.
     > Confirmed via OrcaSlicer testing: pointing this field at the `.py`
     > file directly fails on Windows with `Win32 error: 193` /
     > `ERROR_BAD_EXE_FORMAT` — Python files aren't directly executable, and
     > both slicers try to launch whatever path you give as a program in its
     > own right. `flashforge_gx_post.bat` is a thin wrapper Windows *can*
     > launch, which calls Python internally. PrusaSlicer's own docs suggest
     > its post-processing field accepts a full command line (`python
     > "path\to\script.py"`), which may also work here specifically — but
     > the `.bat` is confirmed working and safer to default to. (Pillow must
     > still be installed for the underlying script — `pip install pillow`.)
     >
     > **`flashforge_gx_post.bat` and `flashforge_gx_post.py` must be in the
     > same folder as each other** — confirmed by real testing (on Orca, but
     > the same wrapper mechanics apply here). The `.bat` finds the `.py`
     > next to itself; if you move/copy the `.bat` without the `.py`, it
     > fails with `Error code: 2`. They can live anywhere as long as
     > they're together.
   - **Output filename format**: change the extension to `.gx`, e.g.
     `{input_filename_base}.gx`.
4. Slice a model. PrusaSlicer writes the `.gx`-named file and calls the
   script, which overwrites it in place with the Flashforge container.
5. Copy the resulting `.gx` file to a USB drive and print it from the
   Creator 4's front panel — **supervised**, since this hasn't been print
   tested yet (see "What's still unverified" below).

## What's still unverified

1. **A PrusaSlicer-sliced file hasn't been printed yet.** The container and
   start/end gcode match a real *FlashPrint* export byte-for-byte, but
   PrusaSlicer's own gcode body (movement/extrusion) has never been run
   through this pipeline and put on the printer. Do a supervised first print
   before trusting this unattended.
2. **Full bed extents and coordinate origin** — only confirmed "centered",
   not the exact usable range or whether the right nozzle's frame is offset
   from true bed-center.
3. **Meaning of `M654`/`M653`/`M656`/`M652`/`M118`** — reproduced with
   observed-working literal values, but not understood. If a print needs
   different fan/filtration behavior than the sample, these may need
   adjusting and nobody currently knows what they do.
4. **PLA (or any non-ABS material)** — the confirmed temps/settings are for
   ABS only; the PLA filament profile included is a reasonable-default
   guess, not verified.
5. **Whether PrusaSlicer's own thumbnail is even present** — if a model is
   sliced without a thumbnail embedded (some PrusaSlicer configs disable
   it), `flashforge_gx_post.py` falls back to a grey placeholder image; this
   is cosmetic only (doesn't affect print correctness) but untested.

## Using OrcaSlicer instead

If you'd rather use OrcaSlicer, see [README-OrcaSlicer.md](README-OrcaSlicer.md)
and `profile/orca_json/` — OrcaSlicer doesn't accept `.ini` bundles like this
one (its importer wants `.json`/`.zip`/`.orca_printer`/`.orca_bundle`/
`.orca_filament`), so that's a separate set of native OrcaSlicer JSON presets
with the same confirmed Flashforge gcode sequence, using OrcaSlicer's own
placeholder syntax for temperatures/bounding-box values. `flashforge_gx_post.py`
itself is shared and works unmodified with either slicer's output.
