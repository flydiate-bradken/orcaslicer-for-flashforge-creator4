# ⚠️ Confirmed not working — kept for reference only

These `.json` files were an attempt at native OrcaSlicer presets, importable
via File → Import → Import Configs. **Tested and confirmed broken**:
importing any of them (including the machine profile) produces "There are 0
configs imported."

Likely cause: these were built by mimicking OrcaSlicer's *source-tree*
profile files (thin JSON with an `"inherits"` chain pointing at internal
base profiles like `fdm_machine_common`), which is a different format from
what the runtime **Import Configs** feature actually expects (probably a
fully-flattened preset with every field spelled out, such as what the app's
own "Export" feature produces from an already-configured preset).

This may not even be specific to these files: the exact error matches a
[known, long-open OrcaSlicer bug](https://github.com/OrcaSlicer/OrcaSlicer/issues/4944)
affecting many unrelated printers/versions, including configs exported from
other OrcaSlicer installs. Import Configs appears to be unreliable in
general (tested against OrcaSlicer 2.4.2).

**Use [README-OrcaSlicer.md](../../README-OrcaSlicer.md) instead** — it has
the same confirmed gcode/temperature/bed values, laid out as manual steps to
enter directly in OrcaSlicer's UI, which is guaranteed to work since it's
just the app's own normal add-printer workflow.

These files are kept here only because the exact confirmed values inside
them (temperatures, bed shape, the Creator 4 gcode sequence) are useful
reference even though the import mechanism doesn't work — and in case
someone figures out the correct flattened format later.
