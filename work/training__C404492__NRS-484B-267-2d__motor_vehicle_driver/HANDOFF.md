# C404492 / NRS 484B.267(2)(d) with (4) handoff

Status: **partial**. Accepted memberships: 0. Frozen `adjacent_lanes/travel_abreast/emergency_vehicle` cell and `motor_vehicle_driver` actor retained. Exact law, qualifying flashing-light reference, source hashes and witness remain in `case-plan.json`.

## CPU construction and evidence

- `draft-emergency-manifest.json` (SHA-256 `2479ad3f15284a977824086d186d0492d5fe899dc2e82d2ad9b626c74eac9cfc`) binds exact controlled primary constructions for following behind (SHA `b1bc8c734c7dacae13344568cbd3941994bddc44257737694032c324e6933bb8`) and closing from behind into longitudinal overlap (SHA `0a22d3eff7b4ecbe9bd025107fc22b32851a3c89b9e970c7616e5022b63233c8`). The second case starts behind; the requested speed policy closes the gap during the recorded episode. Actual motion and overlap are measured after capture. Both bundles passed current pinned offline with `simulation_started=false`; pinned preflight passed.
- `native/runner.py` (SHA `804d6ae139c50b01ea475f4d4fe33e778fe30dbaf45773a97c713d9ce453a472`) is survey-gated for separate subject and authorized emergency vehicle blueprints, adjacent lanes, qualifying light equipment and officer-direction review. It proposes 600 original frames at 20 Hz, four synchronized cameras, observed vehicle pose/extent/velocity and alternating emergency light phase. It has not run in CARLA. Flash authorization and qualifying equipment are independent reviewed facts, not inferred from lamp control or actor name.
- `measure_emergency.py` (SHA `bfd842ca20065ca0b142037a454f0741c443c9e3c7ddcd690ee2cc645f6cbc0f`) joins original frames and actor IDs, requires source-bound authorization, equipment, light phase, moving emergency vehicle and officer-direction context, and reports raw longitudinal intervals/overlap, signed relative order, lateral separation, headings and velocities. It keeps overtaking order crossings separate from abreast overlap and invents no statutory cutoff or legal verdict.
- `prove_emergency.py` tested 600-frame behind versus initial-approach-then-abreast fixtures (0 versus 299 overlap frames), rejecting missing authorization, missing lamp phase and unknown officer direction. Optimized mode passed. `prove_saved.py` decoded four 600-frame diagnostic FFV1 streams, joined source hashes and rejected a changed camera hash. These are synthetic diagnostics, not Native evidence.
- Scoped `worker_check.py --complete` passed (`scoped-check.log`). Strict scoped gate failed on truthful partial status (`strict-check.log`).

## Remaining exact work

Build three distinct fallback candidates per controlled case and strict recipe-backed compatibility; source-review emergency authorization, qualifying flashing equipment, original lamp pixels, officer directions and driver identity; execute original Native same-direction movement and audit approach, body overlap and overtaking separately. Independent statutory and delivery acceptance, accepted recording and GPU queue row remain open. The moving selected branch does not resolve the separate visibly-preparing-to-move statutory alternative.

All scratch, temporary and offline outputs are under `.runtime-work/c404492-267-*`; no temporary directory is under `work/`.
