# training__C229351__LVMC-11-52-040-A__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.52.040(A): Except as otherwise provided in this Chapter: No person shall stand or park a vehicle in a roadway other than parallel with the edge of the roadway headed in the direction of lawful traffic movement.

Cell: road / parallel_park / road_edge; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

vehicle stands or parks in roadway; no chapter exception Vary only `parked_orientation_and_heading` (category) across ['parallel_lawful', 'angled_or_wrong_heading']. Measure parked heading relative to road edge and lawful traffic direction. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Standing and parking should be sampled separately; chapter exceptions need lookup. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## Current CPU foundation (2026-11-23)

Status remains partial. `branch-analysis.json` independently decomposes roadway standing, roadway parking, edge-parallel orientation, lawful-traffic heading and the Chapter-wide exception clause. `case-plan.json` now has three planned parking poses and two comparisons; the reverse-heading pair keeps both poses edge-parallel. None is selected or physically observed. The standing branch and exception applicability still require source-backed case construction.

`parking_measure.py` computes per-frame unsigned edge angle and signed lawful-traffic heading angle from a saved pose extract and independently identified roadway geometry. It hashes the declared Native and geometry sources, rejects missing roadway edge, stale Native hash and unordered frames. The extract itself is not yet independently checked against a real Native trace. It sets no statutory numeric cutoff and does not decide standing, parking, exception or compliance.

CPU command: `.venv-cpu/bin/python work/training__C229351__LVMC-11-52-040-A__motor_vehicle_driver/test_parking_measure.py`; exit 0; log `parking-measure-cpu-test.log` SHA-256 `e286267785fee54b3ea1c1849ae1cf3c6573054ff8d0252eaa9344de15dc2e73`. Code SHA-256 `05a97522147963cd8d39fdb6f3253fec375ee88545afbc3c073cae6d759b7d63`. This is a diagnostic foundation, not the full saved-processing or compatibility proof.

Next worker work: bind the geometry and resting activity to actual Native sources, create exact standing and parking case constructions with a source-resolved Chapter-exception analysis, add four-camera capture and current-runtime primary plus three fallback proofs, then saved processing and independent audits. Run scoped strict gate before any ready promotion.

## Source-bound geometry checkpoint (2026-11-26)

`native/source_audit.py` now binds each of the six planned cases to ordered original Native pose samples, an equal-length four-camera frame join, source-hashed road geometry and the exact survey hash. It rejects a changed road-edge or lawful-direction source, missing camera join, incomplete pose, changed case identity and changed geometry. Its CLI writes the saved pose extract and road-edge context consumed by `parking_measure.py`. `comparison_audit` checks all seven planned case pairs across the six requests and their fixed geometry/survey sources while preserving the measured angle outputs as observations, without a legal verdict. These are CPU code paths and fixture tests; no original CARLA source has been captured.

Proof command: `.venv-cpu/bin/python -m unittest discover -s work/training__C229351__LVMC-11-52-040-A__motor_vehicle_driver/native -p 'test_*.py'`; exit 0; log `native/source-audit-tests.log`; SHA-256 `9ec9e3c52e7908b746c625587944c7e1eb71f90fc834fbb4527d510523684dd2`. Tests include rejection of a missing four-camera join and altered geometry, plus successful handoff to the existing angle measurer. They establish schema and join behavior with synthetic rows only.

The frozen Chapter excerpt includes a Chapter-wide exception clause but does not identify its applicable provision at this location. The [published Chapter 11.52 text](https://library.municode.com/nv/las_vegas/codes/code_of_ordinances?nodeId=TIT11VETR_CH11.52STSTPA_11.52.130POPL&preview=true&site_id=312) identifies § 11.52.010 necessary or directed stops as a Chapter exception requiring a source-specific check. The supplied `inputs/training__C385967__LVMC-11-52-070__motor_vehicle_driver/assignment.json` contains City Traffic Engineer angle-parking designation language. It is a possible relevant provision to inspect during local authority review, not proof of permission for this proposed roadway. A real source survey, governing authority, standing/parking purpose and original video review remain required.

Strict scoped gate: `.venv-cpu/bin/python worker_check.py --assignment training__C229351__LVMC-11-52-040-A__motor_vehicle_driver --complete --require-delivery-ready` still fails because the package is partial. Next CPU actions: construct and offline-check all six exact cases with a common four-camera contract; author source-aware finalization and saved-only processing; add canonical semantic proposals, exact positive/negative compatibility receipts, risk-based fallback proofs, and independent delivery/comparison audit receipts. Do not treat the source-join fixture as any of those receipts.
