# C229404 alley access delivery preparation

Status: `ready` for CPU delivery preparation. The exact scoped strict gate passed with exit 0 on 2026-11-25. No original CARLA recording or statutory blocking finding is claimed.

## Exact cases and law

The four selected cases are `driveway_clear`, `driveway_overlap`, `entrance_clear`, and `entrance_overlap`, each under the assignment prefix. The two comparisons keep the access kind and source-surveyed geometry fixed while varying the parking target. NRS 484B.477(2) requires an alley that is a highway and not a cul-de-sac, a driveway or entrance to abutting property, and actual stopping, standing, or parking that blocks that access. An overlap area is an engineering measurement, never a numeric legal blocking cutoff.

## Completed CPU construction and proofs

- `runner.py`, `carla_alley_adapter.py`, `alley_construction.py`, `parking_controller.py`, and `native_capture.py` implement a reviewed, source-hashed connected-alley packet, surveyed target, 20 Hz approach/stop/park/depart controller, same-tick scene graph capture, original ego footprint/activity, and four synchronized camera archives. Native restoration is checked before seal; `finalize_native.py` encodes lossless four-camera video and seals the capture.
- `analysis.py`, `access_measurement.py`, and `physical_parking.py` assess saved original frame joins, vehicle/access polygon overlap, actual parked hold and motion. They keep physical status separate from the legal blocking judgment.
- Each exact case has a primary and reverse-approach fallback construction. All eight offline checks and all eight positive/negative runtime compatibility checks passed after the final inline construction rebuild. Compatibility exercises selected measurements, Native validation, Lean decoder, Core conversion, four-view rendering, media decode, and missing-source rejection on diagnostic fixtures.
- The semantic delivery chain passed all six stages with four selected cases. The four physical preparation receipts each contain complete, incomplete, and missing-evidence synthetic outcomes plus a real `seal_capture` -> `record_native_exit` -> `acknowledge_owner_release` lifecycle API exercise.
- The four delivery acceptance receipts test source-bound diagnostic analysis and reject diagnostic material for original production delivery. `production_delivery_audit.py` is the independent post-GPU audit: it requires sealed original sources, 900 frame joins, actual physical stop/park/depart, four full lossless video decodes, original camera-to-video pixel checks, and a separate reviewer record bound to the seal and access inventory. The reviewer must determine whether the captured position actually blocked the access. It does not infer that from overlap area.
- The focused CPU suite passed 19 tests. Two focused tests verify that the production audit invokes a full FFV1 decode after counting frames and propagates a decoder failure. `runtime.py preflight` passed with the pinned CPU environment. `execution_manifest.validate`, semantic validation, delivery acceptance validation, and package compatibility validation passed. The exact scoped strict command below passed with `static_checks_passed: true`.

```bash
.venv-cpu/bin/python worker_check.py --assignment testing__C229404__NRS-484B-477-2__motor_vehicle_driver --complete --require-delivery-ready
```

## GPU delivery and review

The original CARLA run must load the reviewed OpenDRIVE and source packet, produce all 900 original frames and four camera archives, close Native ownership, then run saved-only processing and `production_delivery_audit.py` with an independent review record. The record must verify qualifying alley, abutting property and driveway/entrance use, original motion and pixels, and actual blocking or nonblocking. The clear/overlap targets are test designs, not accepted legal outcomes. Lead integrates the shared queue and independently reruns the scoped gate.

## Full-branch saved-processing repair (2026-11-27)

All four exact selected cases now bind `post_capture.command` and `post_capture.feedback_command` to `runtime.py process-saved` with `recorded_only: true`. The commands consume the immutable captured attempt, owner release receipt and Lean validator; they write a separate processed output and do not request another Native run. The commands require the GPU operator to supply `ATTEMPT`, `PROCESSED`, `LEAN_VALIDATOR`, and `OWNER_RELEASE_RECEIPT`.

`.venv-cpu/bin/python work/testing__C229404__NRS-484B-477-2__motor_vehicle_driver/prove_saved_processing.py` passed on all four selected cases after the final manifest binding. It exercised source-shaped synthetic originals for successful saved processing and deleted `original-attempt/alley_geometry.json` in a separate fixture for source-specific feedback. Each positive receipt reported recorded-only processing, original preservation and no physical acceptance claim; each negative feedback receipt identified the missing source and requested no native replay. This is a diagnostic CPU proof, not original CARLA capture or legal blocking review. The log is `cpu-saved-processing-20261127.log`, SHA256 `127e90ee2965526bf40481db753f97c40fd71170ca4f1165c0cdf624b2100674`. The focused suite passed 19 tests after the repair. The exact scoped strict gate passed after the repair with `static_checks_passed: true`; readiness was restored.
