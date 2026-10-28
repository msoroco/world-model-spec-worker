# Partition 04 capability handoff

Exact law: When a vehicle enters an intersection controlled by a traffic-control signal which is installed and has its vehicular signals uncovered, but is inoperative at the time the vehicle enters the intersection, the driver of the vehicle shall proceed as if a stop sign had been erected at each entrance to the intersection and shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After making such a stop, the driver shall proceed cautiously, yielding to vehicles which have previously completed a stop or are within the intersection.

Branch: Blind-intersection post-stop interactions under complete signal inoperability.

The neutral baseline is unselected. Each nonbaseline case has an inline construction and exact SHA in execution-manifest.json. Use `runtime.py offline --manifest work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver/execution-manifest.json --case EXACT_CASE --output NEW_DIRECTORY` for CPU checks. Later operator-owned capture uses `runtime.py capture`; saved conversion and rendering use the supplied `runtime.py process` and `runtime.py render` implementations. `analyze.py --attempt PATH --output REPORT` verifies original channel/frame/video pixels and produces measured results and same-setting follow-up decisions. No simulator ran here.

Public-way and device authority remain explicit synthetic context. Actual map meshing, device assets and states, actor dynamics, body footprints, visibility, duration and final encoded video are unmeasured; capability code records or diagnoses these. No legal verdict or physical acceptance is claimed.

## Update 005

The exact case targets, recording descriptions, and mandatory observations remain frozen. The runner now writes canonical original identities once per tick with `FrameMap`. Its analyzer computes saved measurements, retains unknown physical cause/setup, and uses `write_result` for native output. Owned cleanup actions run independently; `world_restore.snapshot/restore` restores packaged or generated maps with readback, and the runner saves `restoration-receipt.json`. CPU doubles exercise the writer, both world kinds, failed readback, and cleanup continuation. No CARLA run or physical acceptance occurred.

All 2 exact cases passed offline checks. All package compatibility commands ran the actual bundled analysis and native validator, then failed at the frozen converter: ValueError: Unknown required atom: drv.arrival_order. The pinned ontology lacks these mandatory IDs. No source-side channel or fixture can implement an undefined Lean atom. Keep this package partial until the upstream runtime adds support and new compatibility receipts are generated. See `update005-checks.json` for every exact command, exit code, fixture and hashed log.

Physical route behavior, target attainment, sensor framing/visibility, duration and statutory findings remain unresolved for operator-owned execution and review. Public-way and device-authority statements are synthetic context, not measured legal facts.
