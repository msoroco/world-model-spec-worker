# training__C111331__NRS-484B-307-8b__pedestrian

Status: **delivery prepared on CPU**. Five exact cases, ten candidate bundles, and three controlled comparisons are selected. Original Native signals, pedestrian entry, decoded camera pixels, and legal outcomes remain physical review items.

## Exact scope

NRS 484B.307(8)(b) concerns a pedestrian facing a steady red signal who shall not enter the highway unless another device permits proceeding under NRS 484B.283. `case-plan.json` records the selected requirement dispositions and five cases: `condition_a` (outside highway), `condition_b` (entry), `exception_absent` (entry without other-device permission), `exception_permits` (entry with an authored other-device permission request), and `exception_countdown` (entry with an authored flashing countdown request). The latter two are distinct statutory alternatives; no generic CARLA traffic-light state is treated as a legal pedestrian display. The plan also defines the red-entry, other-device-permission, and countdown-permission comparisons. The source term `drv.entering_intersection` is a named derived `first_roadway_footprint_frame` measurement from original walker position/footprint, geometry, FrameMap, and camera joins; it is mapped to mandatory captured channels and the assignment source reference. Missing-original-source negatives are bound for every candidate.

## CPU delivery package

`execution-manifest.json` binds a primary and a spawn-clearance fallback for each case. The ten bundles pass current pinned `runtime.py offline`; their construction, logs, source-hashed public compatibility receipts, missing-original-source negative logs, and recorded-only `process-saved` receipts are bound in the manifest and `proofs/`. Each saved check reports `missing_evidence=false`. Public diagnostic captures are synthetic fixtures; they are not original Native recordings. All four original source camera streams, walker and signal channels, FrameMap, source hashes, and decoded RGB joins remain required by the runner and source audit.

`proposals/semantic-index.json` (SHA-256 `f30302dc5aa4075394fd8394869493755f433d1174212ddb617c7b87b39d5b67`) validates the five canonical proposals, relevance, templates, and bindings. The physical preparation validator passes five synthetic case fixtures. Independent `delivery_acceptance.py` and `comparison_audit.py` pass positive synthetic source checks and missing-source negatives; the three comparisons are source-audited, with governance and pixels reserved for original capture review. `native/prove_native_red.py`, root unit tests, physical proof, and comparison proof pass. The execution manifest SHA-256 is `03ead4147981cc4d9123ae9f715e834e4eddd80dcb545f72ec62469927629945`.

## First physical delivery and review

Use `first_gpu_delivery_command` in `result.json` with a real `$DB`, `$RUN`, `$JOB_ID`, `$CARLA_PYTHON`, `$CARLA_HOST`, and `$CARLA_PORT`. Review the exact governing red head and its facing relationship, actual other-device authority and displayed Walk/countdown pixels, the walker footprint crossing, all four synchronized original camera streams, restored source hashes, and saved measurements before making any observational or legal claim. The planned 30-second four-view camera coverage is in `case-plan.json`.

The exact scoped static readiness check is:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment training__C111331__NRS-484B-307-8b__pedestrian --complete --require-delivery-ready
```
