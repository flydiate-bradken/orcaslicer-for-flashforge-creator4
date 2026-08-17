# Nozzle variant reference table

Single source of truth for how the 0.6mm and 0.8mm profiles were derived from
the 0.4mm baseline. All ratios are scaled from the proven-working 0.4mm
profiles already used elsewhere on this machine (not invented from scratch).
If you want to hand-tune a variant later, this table tells you what to change
and why.

## Machine profiles (`orcaslicer_profiles/machine/`)

| Key | 0.4mm | 0.6mm | 0.8mm | Rationale |
|---|---|---|---|---|
| `nozzle_diameter` | 0.4 | 0.6 | 0.8 | — |
| `max_layer_height` | 0.32 | 0.48 | 0.64 | consistent 80%-of-nozzle ceiling |
| `min_layer_height` | 0.08 | 0.08 | 0.08 | floor unaffected by nozzle size |
| `retraction_length` | 0.3 | 0.45 | 0.6 | bigger nozzle = bigger melt chamber, more oozing risk |
| `retraction_speed` | 45 | 40 | 35 | slightly gentler retraction as volume increases, avoid grinding |
| `deretraction_speed` | 35 | 32 | 28 | paired with retraction_speed |
| `z_hop` | 0.4 | 0.5 | 0.6 | taller layers/wider nozzle body needs more travel clearance |

Everything else (bed shape, `gcode_flavor`, `host_type`, `machine_start_gcode`,
`machine_end_gcode`, extruder posture) is identical across all three and
copied verbatim — gcode doesn't vary by nozzle diameter.

## Process profiles (`orcaslicer_profiles/process/`)

| Key | 0.4mm | 0.6mm | 0.8mm |
|---|---|---|---|
| `layer_height` / `initial_layer_print_height` | 0.20 | 0.30 | 0.40 |
| `line_width` / `outer_wall_line_width` / `internal_solid_infill_line_width` / `top_surface_line_width` / `support_line_width` | 0.4 | 0.6 | 0.8 |
| `inner_wall_line_width` / `sparse_infill_line_width` | 0.45 | 0.68 | 0.9 |
| `initial_layer_line_width` | 0.5 | 0.75 | 1.0 |
| `outer_wall_speed` | 60 | 40 | 30 |
| `inner_wall_speed` / `sparse_infill_speed` / `internal_solid_infill_speed` | 80 | 55 | 40 |
| `bottom_shell_layers` | 3 (0.60mm) | 2 (0.60mm) | 2 (0.80mm) |
| `top_shell_layers` | 4 (0.80mm) | 3 (0.90mm) | 2 (0.80mm) |

Layer height is 50% of nozzle diameter across all three, for consistency.
Line widths follow the ratios already used by the proven 0.4mm process
profile: outer wall / top surface / support ≈ 1.0× nozzle, inner wall /
sparse infill ≈ 1.125× nozzle, initial layer ≈ 1.25× nozzle. Speeds scale
down as nozzle size grows (more volume extruded per mm of travel at the
same speed); shell layer counts are recomputed to hold shell *thickness*
roughly constant rather than layer *count* constant.

## Open questions (see also README.md "Open Questions")

These are genuine unresolved discrepancies between two real FlashPrint 5
`.gx` exports for the Creator 4 examined while building this project. They
are **not** guessed at — each is documented here and a conservative choice
made, so they're easy to find and revisit if a real print reveals the wrong
one was picked.

1. **`M651 Sxxx` vs bare `M652`** immediately before `M108 T0` in the start
   gcode — **now understood, not guessed.** `M651 Sxxx` turns the Creator
   4's case/chamber fan **on** to speed `xxx` (0-255 PWM range); bare `M652`
   turns it **off**. (Earlier research into this pulled up conflicting
   third-party accounts of `M651`/`M652` from other Flashforge model
   families — a coordinate-query interpretation, a "peel move" guess — that
   didn't fit the Creator 4 evidence well; this fan on/off reading is a much
   better fit and is what's used below.)

   This cleanly explains both real samples, and connects to item 4 below:
   the **ABS** sample uses bare `M652` (fan off — standard practice for ABS,
   which wants a warm, still chamber to avoid warping/delamination) *paired
   with* `M653 S55` / `M656 S300` (chamber heat likely on, see item 4); the
   **PLA** sample uses `M651 S255` (fan on, full speed — standard practice
   for PLA, which benefits from active cooling) *paired with* `M653 S0` /
   `M656 S0` (chamber heat off). Both samples' *end* gcode uses bare `M652`
   regardless of material, which also makes sense — turning the case fan
   off is a safe default at shutdown either way.

   **Architecture (as of this revision): moved out of the printer profile
   entirely, into filament profiles.** The printer profile's
   `machine_start_gcode` now ships a material-neutral baseline — bare
   `M652` (fan off) + `M653 S0` / `M656 S0` (chamber heat off) — not itself
   one of the two real samples, but built from two independently-validated
   pieces (each half was confirmed accepted by the printer in at least one
   real sample, just not together). `orcaslicer_profiles/filament/Generic
   PLA @FlashForge Creator 4.json` and `.../Generic ABS @FlashForge Creator
   4.json` layer the real, material-specific pairing on top via
   `filament_start_gcode` (which runs after the printer's start gcode, so it
   can override): PLA sends `M651 S255` (fan on) + `M653 S0` / `M656 S0`
   (redundant with the baseline, kept for clarity); ABS sends `M652`
   (redundant, kept for clarity) + `M653 S55` / `M656 S300` (chamber heat
   on). Swapping only one half of a pairing (e.g. fan on with chamber heat
   also on) isn't a combination either real sample used, which is why both
   filament profiles set all three values together rather than one at a
   time. Select the matching filament profile for your material and this is
   handled automatically — no manual gcode pasting needed.
2. **Trailing `.gx` header int16 field**: `0` in the real ABS sample, `257`
   in the real PLA sample — **the same ABS/PLA split as items 1 and 4**,
   worth checking whether it's another material-dependent field rather than
   arbitrary noise. Re-checked the two samples directly to rule out
   confounds: both use the identical slicer version (`ffslicer 2.4.4`),
   both have raft/support gcode present (an earlier draft of this doc
   incorrectly said the ABS sample lacked a raft — corrected here, it
   doesn't lack one), and both use the identical 0.18mm layer height. With
   those ruled out, material is the cleanest remaining explanation for the
   `0` vs `257` split, though two samples still isn't much to generalize
   from.
   - `257` = `0x0101` in hex — two single bits set (one in each byte of the
     16-bit field), vs. all-clear for `0`. One plausible reading: this
     mirrors the `M651`/`M652` case-fan on/off state from item 1 into the
     header for the printer's LCD to read without re-parsing the whole
     gcode body — the same duplication pattern this header already uses
     elsewhere (nozzle temp is stored twice in the same 8-field block). Not
     confirmed, and there's no way to verify what (if anything) the printer
     actually does differently based on this byte without hands-on hardware
     access.
   - **Known limitation, not currently handled**: now that the PLA/ABS fan
     and chamber-heat behavior lives in filament profiles (item 1), this
     trailing byte stays hardcoded at `0` regardless of which filament
     profile is selected — the post-processing script has no way to detect
     filament-level gcode the way it reads printer/process settings from
     OrcaSlicer's footer comments. If this field does matter, PLA prints
     (using the PLA filament profile's fan-on override) would end up with a
     byte value (`0`) that doesn't match what a real PLA FlashPrint export
     used (`257`). Given the purpose is unconfirmed and likely
     LCD-display-only, this hasn't been "fixed" — fixing behavior for a
     field whose real-world effect is unknown risks trading one unverified
     guess for another.
   **Chosen: `0`** — see `post_processing/flashforge_gx_post.py`.
3. **Bed origin convention**: corner `(0,0)-(400,350)` vs centered
   `(-200,-175)-(200,175)`. **Chosen: centered**, based on real gcode
   coordinates in both samples being small and including negative Y values
   for a small, roughly-centered test part — this is the strongest evidence
   available, but it has not been confirmed with a full-bed-width print.
   If a test print comes out positioned or clipped unexpectedly, this is the
   first thing to check.
4. **`M653`/`M656` values**: `S55`/`S300` in the ABS sample, `S0`/`S0` in the
   PLA sample. Searched specifically for these two codes — no community
   documentation found for either (the newer Flashforge Adventurer
   5M/Guider generation uses an entirely different scheme, `M106 P2 Sxxx`,
   for chamber fan control, confirming the Creator 4's `M65x` range is
   older/model-specific and not something the wider community has covered).
   Best-effort reading of each, at different confidence levels:
   - **`M653 Sxxx` = chamber heater target temperature in °C — fairly
     confident.** `S55` (ABS) vs `S0` (PLA, i.e. off) is exactly the shape
     you'd expect for a temperature target; 55°C is a commonly-cited ABS
     enclosure temperature; the Creator 4's own machine profile already
     declares `"support_chamber_temp_control": "1"`, confirming the
     hardware capability exists; and it sits in the same "declare all
     heater targets" cluster as `M104`/`M140` (nozzle/bed) at the top of
     the start gcode.
   - **`M656 Sxxx` = leading theory: a chamber pre-heat timeout in seconds**
     (`300` = 5 minutes) — `S0` in the PLA sample would then mean "no
     timeout, chamber heat isn't being used anyway." `300` exceeds the
     0-255 range that fit `M651`'s fan-speed parameter cleanly, ruling out
     a PWM/duty-cycle reading; 5 minutes is also a plausible, round
     real-world figure for how long it'd take an enclosed chamber (not just
     a small hotend or bed plate) to come up to temperature, which is why
     this reading make sense. A "wait for chamber temperature" reading
     (parallel to how `M6`/`M7` wait for extruder/bed) was considered but
     doesn't fit the gcode's own positioning: `M656` sits immediately next
     to `M653`, while the real `M6`/`M7` wait-commands are positioned
     several lines later, separated from `M104`/`M140` — a different
     structural pattern than a deferred wait-command would use. Still not
     hardware-confirmed — see the note at the end of this item.
   **Architecture: moved into filament profiles, same as item 1.** The
   printer profile's baseline is now `S0`/`S0` (chamber heat off,
   material-neutral); `orcaslicer_profiles/filament/Generic ABS @FlashForge
   Creator 4.json` sets `S55`/`S300` via its `filament_start_gcode`, paired
   with `M652` (fan off, redundant with the printer baseline, kept for
   clarity) as a matched preset. The most reliable way to actually resolve
   `M656`'s meaning would be sending it standalone to the printer over a
   serial/OctoPrint terminal and watching the front-panel display react —
   not something verifiable without hands-on access to the hardware.
