# NRS 484B.490 narrow-highway parking device handoff

Status: **ready for original Native delivery**. The exact assignment-scoped strict CPU gate passed. No CARLA recording, official-device source, actual pixel review, physical acceptance, or legal verdict is claimed.

## Statute and selected comparison

The source law is NRS 484B.490: an erected official traffic-control device must prohibit parking upon a narrow highway, and the person must park a vehicle upon that highway. The narrow-highway classification, official authority, erection, device content and governed extent are independently source-reviewed terms. The synthetic OpenDRIVE signal requests a scene; it is not evidence of official authority. No width threshold is inferred as a legal cutoff.

Two exact selected cases use one 140 m OpenDRIVE road, 2.8 m lanes, a fixed requested parking-prohibition sign and the same four-view 20 Hz, 30 second camera policy. `__probe_01` requests the parked footprint outside the governed extent at x=35 m; `__probe_02` requests it inside at x=0 m. The paired comparison changes only parking position. `case-plan.json` binds the source observation mapping, branch requirement and independent comparison audit. Neither case has an expected legal label.

## CPU preparation and source gates

`geometry.py` and `runner.py` construct the requested Native map, sign, vehicle and original four-camera capture. `source_review.py` and `finalize.py` require original road geometry, road review, six separately hashed source-context terms, full original frame joins and four video sources before deriving a saved measurement. `parking_saved_measure.py` emits stationary interval and footprint inclusion measurements with `legal_result: null`; missing authority and missing source packets are rejected. Source files and video content remain original-delivery conditions.

Both exact inline constructions passed current-runtime offline preflight. Both passed public compatibility with final decode, selected measurements and missing-source negative rejection, and both passed recorded-only `process-saved` on synthetic original-shaped fixtures. Each case has a physical and lifecycle CPU proof with met, unmet and unverified outcomes. The five-stage semantic proposal chain validated. Independent delivery audits reject synthetic fixture provenance and require original source, owner release, four complete video decodes, per-frame device pixels and source joins. The comparison audit checks fixed road/device/camera/time policy and isolated parking position, with a wrong-pair negative.

All fixture and process output paths were under `.runtime-work/c135709-check`; only proof receipts and logs are returned under this assignment. Synthetic fixtures are diagnostics, not accepted delivery evidence. `execution-manifest.json` binds the current runtime, each exact construction, acquisition source, offline proof, public compatibility and negative proof, saved-only receipt, physical proof and delivery acceptance tests.

## Verification and next action

`SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c135709-check .venv-cpu/bin/python -B worker_check.py --assignment training__C135709__NRS-484B-490__motor_vehicle_driver --complete --require-delivery-ready` exited 0 on the CPU-prepared package. The first GPU command is recorded in `result.json`; execute and accept each selected case only after original Native capture, source review and independent delivery/comparison audit pass. The assignment remains `delivery_prepared` until then.
