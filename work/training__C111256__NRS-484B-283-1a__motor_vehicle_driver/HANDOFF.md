# C111256 / NRS 484B.283(1)(a) CPU checkpoint

Status: **partial**, unselected, four draft cases, zero accepted recordings and zero selected delivery cases. Frozen cell: intersection / travel / crosswalk; actor: motor_vehicle_driver. The exact law and case bindings are in `case-plan.json`. Seven source-topic branches in `statutory-review.json` remain unproven.

## Construction and current checks

The worker-owned Native proposal authors a marked uncontrolled crosswalk, northbound ego route, directional-half pedestrian crossing, original actor/map channels, and four synchronized lossless cameras. The current camera names are `overview`, `approach`, `reference_corner`, and `driver_reference`. `witness_1` yields; `witness_2` overlaps conflict. `exception_1_1` and `exception_1_2` hold trajectories fixed and vary only synthetic blind-person/white-cane declarations. Those declarations do not establish a physical cane or legal eligibility.

The primary and three fallbacks change only one knob each: route lookahead after measured cross-track error >0.45 m, yield clearance margin after measured clearance <1 s, and overview FOV after measured crosswalk/body pixel margin <40 px. Source-hash-bound triggers and all 16 plans are in `native/engineering-plan.json`.

Current scoped CPU checks passed with `.venv-cpu/bin/python`: `build-draft-candidates.py` rebuilt 16 unselected bundles; `run-draft-offline.py` passed 16/16; five `native/test_native.py` tests passed; `saved-fixture-proof.py` passed four 480-frame synthetic saved positives with four decoded cameras and four missing-road-geometry negatives; `audit-native-cpu.py` and `audit-statutory-review.py` passed. The saved fixture now marks invented speed `synthetic_native_sample`; the finalizer names the four current cameras. These checks prove only synthetic CPU paths, with no CARLA execution or original pixels.

The scoped `worker_check.py --complete` gate passes. `--complete --require-delivery-ready` fails as expected because this is a partial package.

The missing retained graph was replaced with worker-authored per-frame ego graphs derived from the same synthetic saved poses and body vertices. `build-diagnostic-recipes.py` creates explicit, hash-bound current-runtime fixture recipes for all four cases. The graph has a diagnostic source label; it is not original CARLA evidence.

Public `runtime.py compatibility` and `runtime.py process-saved` now pass for the primary `witness_1` and `exception_1_2` cases. Compatibility covers actual analysis, Native validation, rebuilt derived channels, four full-resolution cameras, current Lean decoder, render, final decode, selected measurements, unchanged acquisition and missing-`road_geometry.json` negative. Saved processing covers 480 timestamp joins, final decode, no missing evidence and unchanged original sources. Receipt hashes and exact scopes are in `public-runtime-proof.json`; exception case public command output is retained in `public-compatibility-exception12.log` and `public-saved-exception12.log`. The current decoder used is `.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck`; the older November 5 decoder rejected the current manifest as incomplete.

The other two primary cases and all fallback candidates still need public compatibility and saved-processing checks. The old `probe-package.py` invocation and prior v1 package/comparison receipts are historical; rebuild and independently audit all 16 current package diagnostics. The complete selected v2 delivery proof, independent acceptance audit, canonical selected commands and GPU queue row remain to be built.

Unclaimed source alternatives include cited NRS 484B.287 restrictions, NRS 484B.350 school pedestrian lane, opposite-half near-danger crossing and one-way directional-half definition. The NRS 484B.290 white-cane/eligibility condition, real pedestrian behavior, original Native pixels and original actor readback also remain unverified.
