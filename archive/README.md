# Archive — historical / superseded / out of scope

Everything in this folder is kept for reference only. None of it is part of
the active project, none of it is maintained, and none of it should be
copied into OrcaSlicer or relied on for a real print.

- **`PLAN.md`** — the original plan-mode plan, written before a real Creator
  4 sample existed. Several assumptions in it were superseded once real
  hardware output was inspected — see the main [README.md](../README.md).
- **`OrcaSlicer_Reproduction_Plan.md`** — an earlier, more detailed
  reproduction writeup of the OrcaSlicer bridge. Superseded by the current
  [README.md](../README.md) plus [docs/NOZZLE_VARIANT_TABLE.md](../docs/NOZZLE_VARIANT_TABLE.md)
  and [docs/DUAL_EXTRUDER_EXPERIMENTAL.md](../docs/DUAL_EXTRUDER_EXPERIMENTAL.md),
  which reflect what was actually learned from real hardware testing
  afterward.
- **`README-PrusaSlicer.md`** — setup guide for the PrusaSlicer path this
  project used to support. **Out of scope going forward: this project now
  targets OrcaSlicer only.** Kept only in case a PrusaSlicer setup is ever
  needed again.
- **`profile/`** — the PrusaSlicer `.ini` config bundle, plus an
  `orca_json/` folder of early native-OrcaSlicer-format presets that were
  **confirmed not importable** into OrcaSlicer (see `profile/orca_json/README.md`
  inside this folder) — superseded by the working, hand-verified presets in
  [`orcaslicer_profiles/`](../orcaslicer_profiles/).
