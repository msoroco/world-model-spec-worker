# C132497 LVMC 11.43.010(C)(2) handoff

Status: **partial**. Two unselected reference/contrast cases, eight unselected candidate constructions, zero accepted recordings and no legal verdict.

## Source and scope

The frozen law says an operator who intends to exit a roundabout shall use the right lane to turn right. `case-plan.json` binds the exact assignment, witness and topic hashes. The reference requests the right circulating lane; contrast requests the other lane. The comparison changes that lane request, with the road, actor, weather, timing and same-candidate capture profile fixed. The single supplied witness is planning context, and `full-train` has zero accepted membership rows. Intent to exit must be established independently of the request field before a case can support the statute.

## Current CPU construction and proofs

`native/build.py` authors 240-frame entry, clockwise circulation and east right-exit requests for both cases and four candidates. Fallback1 reduces requested speed to 6.5 m/s for measured lane-center deviation over 0.2 m. Fallback2 raises overview capture height for fewer than 20 visible right-lane frames in the first 40. Fallback3 holds the vehicle for two seconds before entry for fewer than 20 stopped frames in the first 40, then completes the same exit route. `native/triggers.py` measures these on source-bound saved diagnostics. No candidate is selected.

`native/capture.py` configures and spawns `overview` at 1920×1080 plus `approach`, `reference_corner` and `driver_reference` at 1280×720. `native/prove_camera_calls.py` exercises all eight camera configuration calls over two profiles, attachment and a rejected failed spawn without contacting CARLA. The Native capture path remains unexecuted. `native/prepare_raw.py` now requires all four named 240-frame FFV1 original streams and source-hashed human right-lane review in original mode.

Run `.venv-cpu/bin/python work/training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver/update015-prove-right-exit-repair.py` to rebuild the copied proof chain. It passes eight source positives, 32 altered-source negatives, 24 raw/saved positives, 32 raw/saved negatives, four synthetic comparison pairs, trigger variants and independent construction, saved, comparison and statutory audits. The current proof is `update015-right-exit-repair-proof.json` and its command details are `update015-right-exit-repair-command.log`. All original-evidence fields remain false.

Run `.venv-cpu/bin/python work/training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver/build-current-offline.py`, then `.venv-cpu/bin/python work/training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver/prove-current-offline.py`. All **8/8** unselected inline constructions pass pinned `runtime.py offline` with their materialized tests. Exact commands, log hashes and construction hashes are in `update015-current-offline-matrix.json`. Generated materializations are under ignored `.runtime-work/`.

These proofs establish source consistency and CPU feasibility of the authored request. The OpenDRIVE currently has a connected south entry, clockwise **quarter arc** and east exit; it is not yet a full physical roundabout. The request field `intended_exit_kind` is not independent intention evidence. Synthetic right-lane occupancy and phase measurements are not actual Native movement, right-turn observation or a legal conclusion.

## Exact next CPU work

Complete the roundabout OpenDRIVE geometry and map connectivity, then rerun Native lane/phase and camera-spawn CPU checks. Derive an independent intention source from the scenario controller or route plan and bind it to raw acceptance. Make the current runtime manifest satisfy `runtime.py compatibility` positive and missing/changed-source negative checks, and run actual `runtime.py process-saved` on four-camera diagnostic sources for the primary and all fallbacks. Implement the original delivery and comparison auditors with stale/missing source negatives, select cases only after the law and witness review is sufficient, and prepare the exact delivery manifest and queue. Rebuild every affected receipt after any construction or case-plan change. Original CARLA motion, complete physical roundabout, lane markings and pixels require later local verification; they do not replace these CPU tasks.

Run `.venv-cpu/bin/python worker_check.py --assignment training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver --complete` after changes. Run its `--require-delivery-ready` form only after the selected CPU delivery package is complete. The full-batch strict gate currently also rejects the frozen `runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` as an unapproved output. This runtime file was left untouched under the user's no-runtime-edit instruction. The batch's other partial/blocked assignments are additional unfinished worker preparation.
