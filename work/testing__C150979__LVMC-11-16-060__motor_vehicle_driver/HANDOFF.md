# C150979 speed and posting delivery handoff

Assignment: `testing__C150979__LVMC-11-16-060__motor_vehicle_driver`.
Status: `ready` for source-gated delivery preparation. The exact assignment strict CPU gate passed on 2026-11-26 with `static_checks_passed: true`. No physical or legal acceptance is claimed.

The four cases are `same25_below` (20 mph requested), `same25_at` (25), `same25_above` (30), and `different35` (30 with a different 35 mph posting). The two comparisons hold route, map, weather and actor context fixed while testing requested speed boundaries and the different posted value. The frozen cell includes a speed-limit sign, so the same-value 25 mph cases do not claim a sign-free street. The exact Title posting authority, jurisdiction, prima facie effect and rebuttal remain unresolved for local review.

`runner.py`, `native_capture.py`, and `native_output_bridge.py` implement a source-hashed reviewed site and operator gate, Native one-way lane and sign readback, 900 original 20 Hz actor samples, four synchronized RGB cameras, capture sealing and restoration. `analysis.py` projects only saved original sources into measured speed and posting channels. Eight primary/fallback bundles passed exact offline and positive/negative compatibility proofs. Four selected cases passed saved-only positive and missing-history negative proofs, synthetic physical/lifecycle probes, and independent delivery full-decode positive/negative audits. Both comparisons passed independent positive/negative audits. The focused test suite passed 13 tests.

`execution-manifest.json` SHA-256: `ab1b44e14d8261b8ba07310d90cf46d24d96eb19bc03c6c366a8705507fbc0ba`.
`gpu-queue-proposal.json` SHA-256: `7d953be3f4c183642b1d28226b9bb7df18cf05edc87e3cb17b3d997ebf51a09a`.

The local delivery runner requires the exact source packet and operator module with their SHA-256 values in `SCENARIO_SPEED_SITE_PACKET`, `SCENARIO_SPEED_SITE_SHA256`, `SCENARIO_SPEED_OPERATOR_MODULE`, and `SCENARIO_SPEED_OPERATOR_SHA256`. The GPU delivery must verify actual measured speed, sign passage and extent, four-view pixels, physical completion and posting authority before an acceptance claim.
