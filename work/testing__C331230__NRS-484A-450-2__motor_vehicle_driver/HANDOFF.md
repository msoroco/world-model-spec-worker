# C331230 near-side crosswalk delivery handoff

Assignment: `testing__C331230__NRS-484A-450-2__motor_vehicle_driver`.
Status: `ready` for source-gated delivery preparation. The exact scoped strict CPU gate passed on 2026-11-26 with `static_checks_passed: true`. No new physical or legal acceptance is claimed.

Exact NRS 484A.450(2) requires a driver approaching a stop-sign intersection to stop before entering the crosswalk on its near side. The no-crosswalk marked-line and nearest-view alternatives remain in the exact semantic template, outside this selected near-side branch. The four selected cases are `marked_crosswalk_halt`, `marked_crosswalk_rolling`, `unmarked_crosswalk_halt`, and `unmarked_crosswalk_rolling`. Three comparisons isolate pre-entry cessation at marked and unmarked crosswalks, then marking at a requested halt. No minimum legal stop duration is invented.

Two frozen accepted metadata entries report 900 frames and identify the marked halt and rolling case names. Their original trace and video bytes are absent from this export, so the package does not infer physical cessation or law-specific coverage from membership metadata. `case-plan.json.evidence_review` binds each demonstrated metadata fact to its frozen source and records the remaining source review gap.

`near_crosswalk.py` checks near-side geometry against the approach and opposing sidewalk connections, retains 900 original 20 Hz front/speed samples, ignores stationary spawn transients, uses measured crosswalk entry, and records pre-entry cessation without a legal judgment. `native_capture.py` checks the reviewed site and independent source files, loaded map, governing sign and Native crosswalk readback before capture, computes the actor front from original bounding-box vertices, records four synchronized cameras, and restores the world. `runner.py` and `native_output_bridge.py` provide the source-hashed Native entrypoint and sealed Core handoff. `analysis.py` performs saved-only source-bound measurement and rejects missing history.

All four primary and four brake-distance fallback bundles passed exact offline and positive/negative compatibility. Four selected cases passed saved-only positive/missing-history negative, synthetic physical/lifecycle, and independent four-view full-decode delivery positive/negative proofs. All three comparisons passed independent fixed-context positive/negative audits. The focused suite passed 11 tests. CPU fixtures remain diagnostic; actual front trajectory, stop-sign governance, camera visibility and physical completion require local original capture and review.

`execution-manifest.json` SHA-256: `7030122d423873ed4c9f4cc63c9afb8582560da0a1ba777408a5d20c65da7ef4`.
`gpu-queue-proposal.json` SHA-256: `dd2233f0ca20374d257f1e799ab0f8533c17502038be85c3427b2ac06ccee59a`.

Local Native execution requires a reviewed site and operator module with exact SHA-256 values in `SCENARIO_CROSSWALK_SITE_PACKET`, `SCENARIO_CROSSWALK_SITE_SHA256`, `SCENARIO_CROSSWALK_OPERATOR_MODULE`, and `SCENARIO_CROSSWALK_OPERATOR_SHA256`. The reviewed site must include the map, actual sign orientation/governance, near-side crosswalk geometry and opposing sidewalk connections. Capture runs at 20 Hz for 900 frames with the four named views; the independent delivery and comparison audits remain required before local acceptance.
