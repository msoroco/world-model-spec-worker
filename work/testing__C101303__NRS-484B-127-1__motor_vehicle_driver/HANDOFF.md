# Partition 04 capability handoff

Exact law: The driver of a vehicle shall not follow another vehicle more closely than is reasonable and prudent, having due regard for the speed of such vehicles and the traffic upon and the condition of the highway.

Branch: Following before a lane change

The neutral baseline is unselected. Each nonbaseline case has an inline construction and exact SHA in execution-manifest.json. Use `runtime.py offline --manifest work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/execution-manifest.json --case EXACT_CASE --output NEW_DIRECTORY` for CPU checks. Later operator-owned capture uses `runtime.py capture`; saved conversion and rendering use the supplied `runtime.py process` and `runtime.py render` implementations. `analyze.py --attempt PATH --output REPORT` verifies original channel/frame/video pixels and produces measured results and same-setting follow-up decisions. No simulator ran here.

Public-way and device authority remain explicit synthetic context. Actual map meshing, device assets and states, actor dynamics, body footprints, visibility, duration and final encoded video are unmeasured; capability code records or diagnoses these. No legal verdict or physical acceptance is claimed.

## Update 005

The exact case targets, recording descriptions, and mandatory observations remain frozen. The runner now writes canonical original identities once per tick with `FrameMap`. Its analyzer computes saved measurements, retains unknown physical cause/setup, and uses `write_result` for native output. Owned cleanup actions run independently; `world_restore.snapshot/restore` restores packaged or generated maps with readback, and the runner saves `restoration-receipt.json`. CPU doubles exercise the writer, both world kinds, failed readback, and cleanup continuation. No CARLA run or physical acceptance occurred.

For `env.wet_road` and `env.ice_or_snow`, the runner uses the shipped RGB/instance calibration before recording, then passes same-frame weather, optical calibration and authored surface hashes through `PipelineCapture.capture(extra=...)`. Its four 3.5 m lane geometry differs from the shipped dry 10 m / 7 m surface helper, so the package records an adapted native material receipt. Actual asset paths and native names must be supplied by the operator in `WORKER_NATIVE_SURFACE_MANIFEST` (or direct `--surface-manifest`) and are checked against the live native object inventory; none are assumed from historical paths. The retained fixture has explicitly synthetic four-lane surface adaptation only.

All 3 exact cases passed offline checks. All package compatibility commands ran the actual bundled analysis and native validator, then failed at the frozen converter: ValueError: Unknown required atom: drv.following. The pinned ontology lacks these mandatory IDs. No source-side channel or fixture can implement an undefined Lean atom. Keep this package partial until the upstream runtime adds support and new compatibility receipts are generated. See `update005-checks.json` for every exact command, exit code, fixture and hashed log.

Physical route behavior, target attainment, sensor framing/visibility, duration and statutory findings remain unresolved for operator-owned execution and review. Public-way and device-authority statements are synthetic context, not measured legal facts.
