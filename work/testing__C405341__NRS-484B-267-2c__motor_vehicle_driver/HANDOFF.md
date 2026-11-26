# C405341 NRS 484B.267(2)(c) delivery handoff

Status: ready, delivery prepared. Frozen assignment SHA256: `6064afd7880b0185db0de8a665f52d6441c3239908b6aa7449d19842b977c432`. The exact scoped strict gate passed on this package. Original CARLA capture and legal or physical judgment remain for the delivery run; no synthetic packet is represented as original evidence.

## Legal scope and cases

The rule concerns a driver approaching an authorized emergency or regulatory official vehicle that is moving or preparing to move with qualifying flashing lights. The driver must be prepared to stop unless directed otherwise by a law enforcement officer. Visible unit movement or a driver hand signal can evidence preparation to move. Actual stopping is not independently required by this clause, and no numeric preparedness cutoff is asserted. Brake lamps alone do not establish unit movement. Qualifying flashing lights remain source gated under DEF-NRS-484A-480-3.

The six exact cases are `visible_movement_brake_response`, `visible_movement_no_brake`, `movement_occluded`, `officer_direction`, `regulatory_official_vehicle`, and `hand_signal_alternative`. The four controlled comparisons are `movement_visibility`, `driver_response`, `officer_direction_exception`, and `vehicle_and_cue_alternatives`. The fixed branches, evidence channels, sources, dispositions, and physical risks are in `case-plan.json` and `execution-manifest.json`.

## Construction and capture

`emergency_construction.py` builds and checks source-gated ego route, authorized unit, qualifying lights, movement/hand cue, officer cue, occluder, and response. `runner.py` is the Native execution bundle entrypoint. `native_packet.py` gates reviewed original source and camera provenance. `analysis.py` joins 900 saved frames and emits a nonclaim physical result. Delivery and comparison auditors require original driver-view pixels, source bindings, matched scene controls, and independently reviewed cue annotations. Synthetic diagnostics have explicit synthetic provenance and are rejected as original delivery evidence.

Four declared physical risks have actual fallback candidates: visible movement/brake response uses a movement-speed adjustment; the occluded case raises occluder height; officer direction and hand signal cases extend cue hold duration. The remaining two cases have no additional candidate-specific physical risk after source gating. Every fallback is bound to its own construction hash and proof receipts.

## CPU proof results

- Pinned runtime preflight: pass.
- Unit tests: 13 pass.
- Current-hash offline construction: 10/10 pass, covering six primary and four fallback candidates.
- Current-hash positive and missing-source negative compatibility: 10/10 pass.
- Recorded-only saved processing: 6/6 pass on synthetic diagnostics, with explicit provenance.
- Physical and lifecycle preparation checks: 6/6 pass.
- Missing-original negative delivery audits: 6/6 rejected as intended.
- Exact scoped strict gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2c__motor_vehicle_driver --complete --require-delivery-ready` exited 0 with `static_checks_passed: true`.

The canonical stage proposals and hash-bound receipts are in this assignment tree. `gpu-queue-proposal.json` supplies six exact Native capture commands and four comparison audit commands. Each original capture requires reviewed authority, light equipment, movement or hand cue, ego approach and driver-view visibility; the independent audits preserve the officer-direction exception and legal uncertainty. The first command is also in `result.json`.
