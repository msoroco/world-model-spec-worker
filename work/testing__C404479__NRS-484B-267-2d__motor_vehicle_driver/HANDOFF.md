# C404479 / NRS 484B.267(2)(d) CPU handoff

Status: ready for Native delivery. Exact assignment strict CPU gate passed on 2026-11-27; log: `.runtime-work/c404479-2d/strict-v8.log`. No physical or legal acceptance is claimed.

The frozen evidence inventory has no accepted recording. The exact C404479 cell has adjacent traversable lanes, an overtaking maneuver, an emergency-vehicle control and an ordinary motor-vehicle driver. The law requires an approach to a moving or visibly preparing authorized emergency or regulatory official vehicle that uses qualifying flashing lights; for same-direction movement the driver must not drive abreast of or overtake it, absent contrary law-enforcement direction. This clause does not itself add a siren or front-red-lamp prerequisite. No numeric gap or overlap duration is treated as a legal cutoff.

Eleven selected cases: moving_hold_behind; moving_overtake; moving_abreast; unit_overtakes_ego; preparing_visible_hand_signal; preparing_visible_vehicle_movement; lights_inactive; lights_unqualified; officer_directs_otherwise; regulatory_official_hold_behind; no_approach. Ten baseline-controlled comparisons hold undeclared conditions fixed. case-plan.json maps each to the no-original-2d-recording gap. Original body polygons and same-direction route tangents distinguish longitudinal overlap, ego behind-to-ahead overtaking, reverse unit overtaking and no approach. Actual original source review remains required.

Source-gated Native construction is in emergency_construction.py, runner.py and native_packet.py. The reviewed packet requires connected adjacent same-direction routes, traversable lanes, body extents, clearance source, target authorization, qualifying flashing equipment, original camera poses and any officer/visible-preparation source. The saved finalizer is analysis.py. Synthetic fixtures in diagnostics/ provide software probes only. All eleven primary and eleven fallback pinned-runtime offline checks passed on the route-projected finalizer; all eleven physical/lifecycle probes passed; ten focused tests passed in cpu-tests.log, including rotated lane geometry, side-independent clearance and the separate visible vehicle-movement cue. Earlier +x-only and ten-case proof versions were superseded. Final v8 passed all 22 primary/fallback compatibility variants, all 11 saved-only positives and missing-source negatives, all 11 independent four-view delivery audits with missing-source negatives, all 10 controlled comparisons, and comparison missing-source/fixed-context negatives. Semantic drafts are under proposals/.

The exact strict assignment gate passed. The source-gated GPU queue proposal remains for later Native execution. Keep scratch under .runtime-work/c404479-2d/ and export SCENARIO_PIPELINE_OUTPUT_ROOT before direct runtime imports.

Strict command: .venv-cpu/bin/python worker_check.py --assignment testing__C404479__NRS-484B-267-2d__motor_vehicle_driver --complete --require-delivery-ready

Remaining local GPU checks: actual target authority and equipment, moving/visible preparation, ego approach, actor body extents and lane clearance, camera pixels, complete overtaking episode, officer context and independent legal review.

## Exact identities and reproducible CPU commands

Cases:

- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__moving_hold_behind`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__moving_overtake`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__moving_abreast`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__unit_overtakes_ego`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__preparing_visible_hand_signal`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__preparing_visible_vehicle_movement`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__lights_inactive`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__lights_unqualified`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__officer_directs_otherwise`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__regulatory_official_hold_behind`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__no_approach`

Comparisons:

- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_moving_overtake`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_moving_abreast`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_unit_overtakes_ego`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_preparing_visible_hand_signal`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_preparing_visible_vehicle_movement`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_lights_inactive`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_lights_unqualified`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_officer_directs_otherwise`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_regulatory_official_hold_behind`
- `testing__C404479__NRS-484B-267-2d__motor_vehicle_driver__hold_vs_no_approach`

Run from the repository root with `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c404479-2d/output-root"`, `TMPDIR="$PWD/.runtime-work/c404479-2d/tmp"` and `PYTHONDONTWRITEBYTECODE=1` exported:

- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/build_diagnostics.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/build_constructions.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/build_semantic_proposals.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_offline.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_fallback.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_physical.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_compatibility.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_saved.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/prove_audits.py`
- `.venv-cpu/bin/python work/testing__C404479__NRS-484B-267-2d__motor_vehicle_driver/build_queue_proposal.py`

The positive and missing-source compatibility receipts are in `cpu-compat-*`; saved-only positive/negative logs are in `cpu-saved-*`; independent source/video audits are in `cpu-delivery-*` and `cpu-comparison-*`. The source-gated four-camera local commands are proposed in `gpu-queue-proposal.json` and are unexecuted here.
