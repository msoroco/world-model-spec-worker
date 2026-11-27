# C3997 NRS 484B.587(2)(b) delivery handoff

Status: CPU delivery prepared. The exact scoped strict gate passes. No physical CARLA run or legal acceptance is claimed.

## Source and branch coverage

The exact assigned prohibition is driving across a solid white line separating a marked traffic lane from an entrance or exit lane on a controlled-access highway. The source inventory has no accepted recordings. The cases retain public-authority controlled-access status, public-highway boundary, lane functions, finite solid-white marking geometry, driver/vehicle identity, original body trajectory, emergency necessity and the distinct subsection 3 signed paved shoulder context. Subsection 3 and the appended subsection 1(c)(1) shoulder exemption are not treated as crossing permission. No numeric legal threshold or exact-law judgment range was supplied.

Ten selected exact cases:
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_traffic_stay`: north traffic-lane stay control beside solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_traffic_to_entrance`: north traffic to entrance across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_entrance_to_traffic`: north entrance to traffic across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_traffic_to_exit`: north traffic to exit across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_exit_to_traffic`: north exit to traffic across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__south_traffic_stay`: south traffic-lane stay control beside solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__south_traffic_to_entrance`: south traffic to entrance across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__south_traffic_to_exit`: south traffic to exit across solid-white separator
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_traffic_to_exit_emergency`: north traffic to exit across solid-white separator with contemporaneous emergency necessity
- `testing__C3997__NRS-484B-587-2b__motor_vehicle_driver__north_traffic_to_exit_shoulder_authorized`: North traffic-to-exit solid-white crossing with separately sourced subsection 3 qualifying vehicle and signed paved shoulder context; subsection 3 does not itself authorize this crossing

Nine source-isolated comparisons:
- `north_entrance_vs_stay`: destination; fixed source hashes and other conditions audited.
- `north_exit_vs_stay`: destination; fixed source hashes and other conditions audited.
- `north_reverse_entrance`: origin, destination; fixed source hashes and other conditions audited.
- `north_reverse_exit`: origin, destination; fixed source hashes and other conditions audited.
- `approach_entrance`: approach; fixed source hashes and other conditions audited.
- `approach_exit`: approach; fixed source hashes and other conditions audited.
- `south_entrance_vs_stay`: destination; fixed source hashes and other conditions audited.
- `emergency_exception`: emergency_required; fixed source hashes and other conditions audited.
- `shoulder_scope`: vehicle_class, subsection3_shoulder_authorized, shoulder_paved, lawful_sign_permits_shoulder; fixed source hashes and other conditions audited.

## Construction and measurements

`reviewed_site.py` loads an independently reviewed, source-hashed packet. `outside_lane.py` checks exact C3997 cell identity, north/south sourced routes and their intersection with the finite painted segment; a stay control remains on one side. `lane_native.py` records 900 original 20 Hz frames, body bounding-box vertices, signed and longitudinal segment coordinates, four synchronized cameras, Native trace and source receipt, then restores world settings and releases owned actors. `analysis.py` finalizes from saved original sources only; `saved_audit.py` enforces frame/source continuity. The legal judgment remains null. A single fallback changes only the source-bound steering gain after route convergence or camera coverage feedback, preserving every comparison variable.

## CPU proof map

`execution-manifest.json` binds ten primary and ten fallback constructions, each with offline and positive/negative compatibility receipts. `proof-saved-*.log` proves per-case recorded-only processing and missing-source feedback. `physical-*-receipt.json` binds complete/incomplete/missing-evidence fixture checks and owner-release lifecycle ordering. `delivery-acceptance-*.json` binds independent positive delivery protocol and missing-view rejection; `delivery_audit.py` requires original Native provenance, complete frame/video joins, four-view original pixels, solid-white visibility and sign visibility for the shoulder-context case. `comparison-proposal.json` binds all nine positive and stale-source negative audits. `proposals/semantic-index.json` binds the canonical draft stage chain. All fixtures are synthetic CPU protocol tests, not physical evidence.

## Local execution and validation

`result.json.first_gpu_delivery_command` is the first exact canonical dispatch; supply a reviewed C3997 source packet through `C3997_REVIEWED_SITE` and local CARLA variables. Run the ordered commands in `gpu-queue-proposal.json` after lead integration. Original motion, marking continuity, body crossing within the finite painted extent, exception context, four-view pixels and physical completion require local independent review before acceptance.

`cpu-tests.log`: nine passing unit tests. `strict-check.log`: `.venv-cpu/bin/python worker_check.py --assignment testing__C3997__NRS-484B-587-2b__motor_vehicle_driver --complete --require-delivery-ready` exit 0. The package was checked against the current runtime and all returned files remain textual.
