# training__C229987__NRS-484B-450-1g__motor_vehicle_driver

Status: **partial**. The strict delivery-ready gate has not passed. No Native recording, accepted evidence, statutory verdict or full branch completion is claimed.

## Frozen source and selected probes

NRS 484B.450(1)(g) prohibits a person from stopping, standing or parking a vehicle within 30 feet upon the approach to an official traffic-control signal located at the side of a highway, subject to necessary traffic conflict, compliance with law, police direction and official traffic-control-device direction exceptions. Exact assignment: `inputs/training__C229987__NRS-484B-450-1g__motor_vehicle_driver/assignment.json` (SHA-256 `d1c702e079fc386a31674cd406f6087a994a051efa247f940e92ff6fe3d851f0`). Cell C229987 is road / stop_stand / traffic_light, actor motor_vehicle_driver. No accepted recording inventory exists for this assignment; full-train membership is empty.

`case-plan.json` contains three exact requested front-edge distance cases: `training__C229987__NRS-484B-450-1g__motor_vehicle_driver__25`, `__30`, `__35`, with one controlled comparison. These request below/at/above the 30-foot statutory number; the requested positions are not observed distances or legal outcomes. `analysis/signal_approach.py` and `native/finalize.py` measure original four-corner footprint and signal roadway station per frame, preserve geometric uncertainty and low-speed samples, and separate context review from physical motion.

## Implemented CPU preparation

- `native/25-construction.json`, `native/30-construction.json`, `native/35-construction.json` inline exact case bundles. `native/runner.py` authors OpenDRIVE and the roadside signal, reads the Native signal actor and governed approach lane, drives the subject toward a requested halt, records original pose, footprint, trace and four synchronized camera streams, and seals capture after resource restoration. Root `construction.json`, `config.json`, `runner.py` and `finalize.py` bind the first exact case.
- `native/{25,30,35}-offline.log` contain passing pinned-runtime offline construction checks. `compatibility/{25,30,35}/compatibility.json`, `analysis.log` and `negative.log` contain current construction-bound positive Core/video processing and required missing-`signal_raw.json` rejection. Fixture sources/recipes are under `native/diagnostic/{25,30,35}` and are synthetic only.
- `saved/{25,30,35}-processing.json` and matching logs record passing `runtime.py process-saved` fixture runs. Saved processing versions and videos remain in `.runtime-work/c229987/saved-v7-{25,30,35}`. These prove recorded-only code execution and preservation of fixture acquisition.
- `proposals/semantic-index.json` binds pinned semantic relevance, template, binding and exact-case proposals. The template retains the literal prohibition, 30-foot condition and all four exception clauses. The current selected proposals exercise the distance contrast only.
- `physical_preparation.py` and `physical-proof/{25,30,35}/proof.json` exercise synthetic complete/incomplete/missing physical predicates and Native closure ordering. `delivery_audit.py` and `delivery-proofs/` exercise positive and negative original-source acceptance predicates. `comparison_audit.py` and `comparison-proof/` check source-shaped fixed road, signal, camera and context conditions while the requested and observed diagnostic gaps vary. None is original physical evidence.

Focused checks: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B -m unittest discover -s work/training__C229987__NRS-484B-450-1g__motor_vehicle_driver/tests -v` (2 passed; `cpu-tests.log`), current scoped static check, three offline checks, three compatibility checks, three saved-processing checks, semantic stage validator, execution-manifest validator, three physical proof validators and three delivery predicate validators. The exact strict command presently fails because `result.status` remains correctly partial.

## Remaining CPU work

1. Independently finish the stop/stand/park and necessary-conflict/other-law/police/device branch contrasts from the exact statute. Extend `case-plan.json`, canonical cases and Native constructions with controlled physical circumstances and source packets. The current three distance probes do not establish affirmative exception contrasts or a parking mode. Do not treat an unresolved judgment as a deterministic legal label.
2. Assess the concrete stopping-overshoot risk and test an engineering fallback for each linked case if justified; preserve the comparison variable, camera plan and law/cell/actor identities. The current `candidate_risk: none` is provisional.
3. Rebuild and bind selected offline, positive/negative compatibility, saved-only and physical proofs for any changed construction. Keep source hashes and exact manifest paths aligned. Implement independent original comparison audit invocation in the queue through the lead.
4. CPU-test `delivery_audit.py` against source-shaped original-review and missing/stale-source cases beyond its current predicate self-tests; retain source decode receipt fields under local operations. Fill remaining execution manifest acquisition and acceptance details as validated.
5. Review original law and definitions again, run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B worker_check.py --assignment training__C229987__NRS-484B-450-1g__motor_vehicle_driver --complete --require-delivery-ready`, and set `ready` only when it passes.

Actual CARLA motion, actor readback, pixel visibility, source review and acceptance remain later local checks; they are not reasons to omit the CPU work above.
