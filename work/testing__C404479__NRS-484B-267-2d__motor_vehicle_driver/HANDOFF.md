# C404479 / NRS 484B.267(2)(d) CPU handoff

Status: partial while current-runtime compatibility and delivery proofs run. No physical or legal acceptance is claimed.

The frozen evidence inventory has no accepted recording. The exact C404479 cell has adjacent traversable lanes, an overtaking maneuver, an emergency-vehicle control and an ordinary motor-vehicle driver. The law requires an approach to a moving or visibly preparing authorized emergency or regulatory official vehicle that uses qualifying flashing lights; for same-direction movement the driver must not drive abreast of or overtake it, absent contrary law-enforcement direction. This clause does not itself add a siren or front-red-lamp prerequisite. No numeric gap or overlap duration is treated as a legal cutoff.

Ten selected cases: moving_hold_behind; moving_overtake; moving_abreast; unit_overtakes_ego; preparing_visible_hand_signal; lights_inactive; lights_unqualified; officer_directs_otherwise; regulatory_official_hold_behind; no_approach. Nine baseline-controlled comparisons hold undeclared conditions fixed. case-plan.json maps each to the no-original-2d-recording gap. Original body polygons and same-direction route tangents distinguish longitudinal overlap, ego behind-to-ahead overtaking, reverse unit overtaking and no approach. Actual original source review remains required.

Source-gated Native construction is in emergency_construction.py, runner.py and native_packet.py. The reviewed packet requires connected adjacent same-direction routes, traversable lanes, body extents, clearance source, target authorization, qualifying flashing equipment, original camera poses and any officer/visible-preparation source. The saved finalizer is analysis.py. Synthetic fixtures in diagnostics/ provide software probes only. All ten primary and ten fallback pinned-runtime offline checks passed; all ten physical/lifecycle probes passed; four focused tests passed in cpu-tests.log. Current-runtime compatibility is running. Semantic drafts are under proposals/.

Next CPU actions: complete all 20 primary/fallback compatibility receipts; run prove_saved.py; run prove_audits.py with the independent body-order comparison audit; build_queue_proposal.py; review exact law/source semantics; run the exact strict gate and repair any failure. Keep scratch under .runtime-work/c404479-2d/ and export SCENARIO_PIPELINE_OUTPUT_ROOT before direct runtime imports.

Strict command: .venv-cpu/bin/python worker_check.py --assignment testing__C404479__NRS-484B-267-2d__motor_vehicle_driver --complete --require-delivery-ready

Remaining local GPU checks: actual target authority and equipment, moving/visible preparation, ego approach, actor body extents and lane clearance, camera pixels, complete overtaking episode, officer context and independent legal review.
