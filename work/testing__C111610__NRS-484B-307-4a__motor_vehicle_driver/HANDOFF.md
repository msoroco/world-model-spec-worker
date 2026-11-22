# testing__C111610__NRS-484B-307-4a__motor_vehicle_driver

Status: **ready for Native delivery**. The assignment strict CPU gate passed:

```sh
.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-307-4a__motor_vehicle_driver --complete --require-delivery-ready
```

The frozen law NRS 484B.307(4)(a) requires an official sole green turn arrow facing ego, motion only in its illuminated direction, yield to pedestrians lawfully within the adjacent crosswalk, and yield to other traffic lawfully using the intersection. No numeric legal right-of-way threshold is claimed. `AGENT_PROMPT.md` is absent from this checkout; `START_HERE.md` and frozen inputs govern this checkpoint.

## Exact cases and coverage

- `testing__C111610__NRS-484B-307-4a__motor_vehicle_driver__crosswalk_clear_turn`: ego left turn under a source-verified sole left arrow with adjacent marked crosswalk clear and other lawful traffic absent.
- `testing__C111610__NRS-484B-307-4a__motor_vehicle_driver__crosswalk_occupied_yield`: same map, signal, turn, cameras and duration, with a pedestrian entering under an original Walk indication; ego holds until the lawful adjacent-crosswalk occupant clears.
- `testing__C111610__NRS-484B-307-4a__motor_vehicle_driver__lawful_traffic_yield`: same sole-arrow ego turn and clear adjacent crosswalk, with a second vehicle entering on an original official green head along a connected route before the arrow-phase encounter; ego holds until the other vehicle clears the intersection.

`case-plan.json` maps all three statutory requirements to these exact cases. `adjacent_crosswalk_lawful_occupancy` compares the clear and occupied pedestrian cases. `other_lawful_traffic_presence` compares clear and lawful-traffic cases. `comparison_audit.py` remeasures original sources, checks fixed map, arrow, turn, camera and duration conditions, and verifies only the declared participant difference. Both comparisons have positive and changed-condition CPU tests.

## Construction and CPU evidence

`runner.py` source-gates the ego-facing sole arrow and holds for lawful pedestrians or other vehicles. `native_capture.py` binds a connected Native left-turn route, marked adjacent crosswalk, original arrow asset, occupied-case Walk entry, and traffic-case original green entry and connected other-vehicle route. It stages participants, records entry histories, captures 30 seconds of frame-joined motion and four FFV1 cameras, hashes original acquisition, and seals after resource cleanup and world restoration. Its pedestrian and traffic lifecycle paths run in a fake-world CPU test. Map and phase incompatibility fail closed.

`analysis.py` checks original SHA256s, signal identity and frame, participant entry source, body/time joins, ego hold and clearance, turn heading and duration. It writes source-bound channels, context and measured outputs without a legal verdict. `delivery_audit.py` independently checks the Native seal, exit, owner release, original sources, saved receipt, frame joins, route geometry and full decoded-media receipt. It rejects a diagnostic fixture as Native delivery. The decoded-pixel checker establishes nonblank source data; participant visibility remains physical review.

`execution-manifest.json` binds three primary and three measured steering-fallback constructions. `fallback1` changes bounded steering divisor 45 to 35 only when original 30-second heading change is below 45 degrees or travel is below 5 m. Each case and candidate passed exact offline, synthetic physical-preparation met/not-met/unverified, and pinned positive/negative compatibility checks. All three primary cases passed canonical `process-saved` on diagnostic sources and independent positive/negative decoded-media audit CPU probes. The fixtures explicitly claim no Native physical acceptance. `semantic_delivery.validate` passed six stages and three selected cases; `execution_manifest.validate`, all three `delivery_handoff.validate_case` checks and `package_compatibility.check_receipts` passed. `cpu-tests.log` records **23 passing tests** and its hash is bound in `result.json`.

Rebuild and proof commands for a changed authored source:

```sh
.venv-cpu/bin/python work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/refresh_package.py
.venv-cpu/bin/python runtime.py compatibility --manifest work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/execution-manifest.json --case <exact-case-id> --output .runtime-work/<fresh-output> --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck --candidate <primary-or-fallback1>
.venv-cpu/bin/python work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/record_compatibility.py
.venv-cpu/bin/python work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/refresh_saved.py
.venv-cpu/bin/python work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/refresh_audit.py
.venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/tests -v
```

The first Native job is in `result.json.first_gpu_delivery_command`. The operator supplies `LOCAL_ROOT`, `DB`, `RUN`, `JOB_ID`, `CARLA_PYTHON`, `CARLA_HOST` and `CARLA_PORT`. Before recording, confirm an actual map with the official ego-facing sole left arrow, marked adjacent crosswalk, and an original official green entry phase for the second vehicle followed by an ego arrow phase. The Native binder rejects unsupported assets or timing. Review realized motion, participant visibility, four-camera pixel coverage, duration, lawful entry and right-of-way from the original recording. These are physical checks, not claims established by CPU fixtures.

The complete-batch strict gate still fails while other assignments remain partial. No frozen inputs, runtime files or `batch.json` were edited. No Git command was run; the independent timer publishes work checkpoints.
