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
