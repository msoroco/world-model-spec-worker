# C111325 / NRS 484B.257(1) CPU checkpoint

Status: partial. None of the twelve planned cases is selected for delivery. No original Native event, legal verdict, physical success, or accepted-recording reuse is claimed.

The frozen witness is a stop sign, marked stop line, and through-highway occupancy in cell C111325. The exact statute also covers the yield-sign alternative, the stop-line/crosswalk/nearest-viewpoint hierarchy, the duty while crossing or within the intersection, and police and signal-control exceptions. Existing nine demo and nine full-train membership rows are not source-hashed proof of what those recordings show; inspect the frozen evidence inventory before allocating duplicate recordings.

## Constructed diagnostic

`stop_yield_scene.py` authors perpendicular roads, a governing STOP sign, a marked approach line, a through-highway vehicle, distinct ego controller policies, and the canonical overview/approach/reference_corner/driver_reference cameras for 600 frames at 20 Hz. `measure_stop_yield.py` requires hashes of original map, sign, line, road, vehicle bodies/motion, control state and visibility, joins every Native frame to four camera identities, and measures front-bumper line crossing, recorded pre-line rest, the full intersection crossing interval, and simultaneous through-vehicle occupancy. `stop-yield-measurement-contract.json` records the engineering diagnostics and unresolved legal judgments.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_stop_yield.py`. The generated `stop-yield-proof.json` contains source-shaped synthetic fixtures for `complete_stop_then_yield` and `roll_through_conflict`, plus six negative source, control, frame and camera tests. Fixture hashes and motion are synthetic; the proof is not an exact runtime offline/compatibility or process-saved receipt.

## Source review and statutory plan

`case-plan.json.evidence_review` inspects all nine unique accepted membership rows against their frozen review summaries and hashes. The frozen summaries describe requested stop actions, four stopping-reference alternatives and three through-traffic phases; most hazard/yield judgments are unresolved. They do not supply original Native packet hashes or independently audited full crossing histories. No equivalence reuse is asserted. The five explicit gaps and each case gap ID are in the plan.

Twelve exact cases and eight controlled comparisons now account for STOP versus YIELD, the stop-line/crosswalk/nearest-viewpoint hierarchy, through-highway entered versus approaching traffic, continuing duty while within the intersection, and separate officer/signal control exceptions. `stop_yield_scene.py` emits source-distinct requests for each, including a transverse OpenDRIVE `roadMark` stop-line object or a near-side crosswalk object where applicable; `prove_branch_requests.py` checks all twelve requests and rejects missing crosswalk, viewpoint, exception source and altered governing sign. These remain authored scene requests, not CARLA-validated exact runtime constructions.

## Remaining CPU work

Acquire original accepted recording source packets if reuse is pursued; current summaries do not justify reuse. Select exact cases, implement the pinned runtime construction/controller and source acquisition, run exact offline and positive/negative compatibility for primary and risk-based fallbacks, run actual saved processing, then implement independent delivery and comparison audits and semantic proposals. Promote only after the scoped strict gate passes. CARLA execution, pixel review and canonical acceptance remain local operator work.

## Latest CPU checks

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_branch_requests.py`: passed twelve scene requests and nine negative checks.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_stop_yield.py`: passed two source-shaped diagnostics and six negative checks.
- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/nrs257-output TMPDIR=$PWD/.runtime-work/nrs257-tmp .venv-cpu/bin/python -B worker_check.py --assignment training__C111325__NRS-484B-257-1__motor_vehicle_driver --complete`: passed static partial check.

## Saved-source measurement core

`measure_statutory.py` measures each of the twelve exact planned branches from 600 joined 20 Hz source rows. It records governing sign, reference hierarchy, original body extents, pre-reference rest, full intersection occupancy, through-highway entered/approaching frames, and source identities. Officer or signal control is a distinct observed exception. It never assigns an immediate-hazard or legal verdict. `measure_saved_packet.py` checks the bytes of seven declared saved source files and a 600-row motion packet before calling the meter; paths cannot escape the saved attempt. This is a reusable CPU core for later exact finalizers, not a runtime compatibility or accepted Native receipt.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_statutory_measurement.py`: twelve source-shaped measurements and seven negative checks passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_saved_packet.py`: twelve saved packet byte-bindings and changed/missing-source, wrong-case and path-escape rejection passed. Disposable packets were created only under `.runtime-work/`.

## Diagnostic comparison isolation

`audit_diagnostic_comparisons.py` checks the eight planned comparisons against fixed map, body, sign, reference, through-motion, subject-motion and exception-control sources as appropriate. `prove_comparisons.py` passes all eight with synthetic saved observations and rejects eight altered fixed/difference conditions plus all eight when original Native source is required. It does not count as a production comparison audit or accepted recording; `comparison_audits_passed` remains zero. The through-highway phase and across/within diagnostics now vary only through-vehicle timing while holding the subject motion fixed.

The authored camera requests and diagnostic source joins now use the pinned four-view capture names and resolutions (1920×1080 overview, three 1280×720 details). The saved meter still needs actual source video files and runtime decode before any selected case can be ready.

The yield-sign branch also has its own no-line crosswalk and no-line/no-crosswalk viewpoint cases. This applies the statutory reference hierarchy to both STOP and YIELD without assuming those cases were covered by the existing accepted-recording summaries.

The two control-exception requests now include an explicit officer actor request or a dynamic OpenDRIVE traffic-signal object plus required original direction/state readback. The CPU scene validator rejects missing officer geometry or a missing signal object. This only authors prospective exception construction; an actual controlling official, signal state, device visibility and CARLA lifecycle remain unverified.

## Draft exact capture contract

`config.json` fixes the twelve exact case IDs, the law/cell/actor identity, a common 20 Hz 30-second four-camera profile, and the source-shaped recording description. `case-plan.json.camera_plan` identifies subjects and full intervals for each view. `prove_capture_design.py` checks the case/scene/camera joins and rejects an omitted case, wrong camera resolution and a fabricated physical-acceptance claim. This is a partial design only: it has no selected Native runner or exact runtime offline/compatibility proof.

The through-vehicle phase and across/within request pairs hold the complete-stop subject controller and release frame fixed, changing only the through-vehicle starting station. The source-shaped diagnostic mirrors that isolation; actual motion remains unverified.

## Native construction lifecycle

`native_construction.py` lazily calls CARLA only inside `constructed_scene` on a dedicated local server. It materializes the authored OpenDRIVE, requires map readback of the two roads, governing sign, applicable line/crosswalk and signal, creates subject/through actors, an officer actor for that exception request, and all four configured camera sensors. Synchronous settings, actor teardown and camera teardown are restored in `finally`. `prove_native_construction.py` uses a fake CARLA client to exercise all twelve cases, cleanup and seven missing-source/geometry/spawn failures without starting a simulator. This is construction CPU proof only: no Native motion, source pixels, full capture or canonical acceptance is claimed.

The Native map readback also checks the sign station/orientation and line or crosswalk station/width; fake tests reject displaced objects. Actual CARLA serialization and pixels still need local review.

## Native capture and exact primary offline checkpoint

`native_capture.py` and `runner.py` implement a fresh-attempt, same-tick 600-frame capture through `PipelineCapture`. They request distinct stop and roll controls, preserve source actor body and motion telemetry, SHA-bind seven saved sources, hash each original RGB image, encode all four FFV1 streams, and check 600 decoded frames. Original source capture and pixel review remain unrun. Officer and signal exception captures reject until per-frame authoritative direction or indication is implemented; no legal verdict or physical success is claimed.

`execution-manifest.json` and `construction.json` now bind the complete-stop selected primary to the current runtime and inline runner, constructor, scene, config and three focused CPU tests. `.venv-cpu/bin/python -B runtime.py offline --manifest work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json --case training__C111325__NRS-484B-257-1__motor_vehicle_driver__complete_stop_then_yield --output .runtime-work/nrs257-offline-primary-1` passed without a simulator; retained log: `native-offline-primary.log`. This is a draft one-case construction, not full manifest coverage or public compatibility.

## Selected saved-only finalizer checkpoint

`finalize.py` reads the exact saved packet, joins all 600 motion, frame-map and Core trace rows, requires four decodable 600-frame camera sources, checks original per-frame RGB hashes, Native evidence frame IDs, actor body extent consistency and map/control byte identity when source provenance is Native, and writes result/report files without a legal or physical-success claim. `measurement-complete_stop_then_yield.json` binds all four selected requirement dispositions to separate methods, output keys and exact input paths. `prove_finalize.py` passed four source-bound diagnostic measurements through the runtime measurement-contract verifier and rejected a missing governing-sign source. This is analysis CPU proof; public converter/video compatibility and original Native acquisition remain pending.
