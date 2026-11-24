# testing__C229398__NRS-484D-165-3__motor_vehicle_driver

Status: partial. Exact static check passes; strict delivery gate fails on partial status. No accepted recordings are available for reuse.

## Coverage and source review

The exact NRS 484D.165(3) text incorporates subsection (1) lamp properties and references the times in NRS 484D.100(1). The source-hashed witness is conditional: C229398 curb parking may intersect traveled roadway or adjacent shoulder, but site, timing, illumination and visibility facts must be measured. `case-plan.json` maps six exact cases: `dark_lamps_on`, `dark_lamps_off`, `dark_attended`, `dark_traveled`, `sufficient_light`, and `outside_referenced_time`. It has five controlled comparisons: lamp activation, attendance, placement, 1,000-foot revelation precondition and referenced time. All six are planned new captures; there are zero frozen accepted recordings. The 1,000 and 500 foot distances are statutory observation stations, not invented photometric cutoffs.

## Implemented CPU construction and proof

`execution-manifest.json` binds six exact inline bundles under `construction-*.json`; each materializes its own `runner.py`, source checker, exact `config.json` and focused bundle test. All six exact `runtime.py offline` checks pass (`proof-*.log`), with generated trees kept under `.runtime-work/`. The Native runner now checks a SHA-sealed independent site document, exact CARLA OpenDRIVE bytes, synchronous 20 Hz world settings, source-specified four-camera station transforms and a 900-frame capture. `native_capture.py` retains per-frame vehicle position, velocity, brake and lamp readbacks, four original PNG image streams and a sealed frame map. `carla_cameras.py` binds actual CARLA RGB callbacks to the world frame; `encode_original.py` checks all original images and losslessly encodes four FFV1 views. The runner has not yet completed the pinned Native result/capture-seal lifecycle or process-saved compatibility. `finalize_original.py` joins a saved site packet, 900-frame original history, frame map, four camera seals and case identity; its positive/negative test rejects a stale original history. `parked_lamps.py` verifies source-sealed highway, curb boundaries, traffic side, referenced time, lamp installation, map identity and 1,000/500 foot station locations before Native spawn. Its lazy `construct` spawns a vehicle at a source-specified shoulder or traveled transform, applies the parking brake, sets lamps and reads back Native lamp state. Its `measure` requires 900 contiguous original frames at 20 Hz with parking, lamp, light, time, station and source-camera records. It records unknown photometric observations without assigning a legal verdict. `audit_saved_capture` independently checks sealed original frame-map and four named camera sources; `audit_comparison` checks exact members, original evidence, the fixed source-backed site signature and declared differences. It permits different sealed lighting or referenced-time documents only when that condition is the declared comparison variable.

Eighteen focused CPU tests pass, including Native fake construction of both placements, all six original-frame variants, negative missing source, lamp state, frame-gap and camera cases, and both lamp/time comparison isolation checks. New negative tests reject a changed independent source, mismatched original camera frame, frame gap, and altered original image. A three-frame FFV1/ffprobe smoke check passed in `.runtime-work/`; it is a codec diagnostic, not a case compatibility receipt. Synthetic receipts are software fixtures only.

## Exact commands and logs

- `.venv-cpu/bin/python runtime.py preflight` — pass; `cpu-preflight.log`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229398__NRS-484D-165-3__motor_vehicle_driver/tests -v` — 18 tests pass; `cpu-tests.log`.
- Six case-specific `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C229398__NRS-484D-165-3__motor_vehicle_driver/execution-manifest.json --case EXACT_CASE --output .runtime-work/c229398-offline-v3-CASE --python ABSOLUTE_VENV_PYTHON` checks — all pass; `proof-*.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484D-165-3__motor_vehicle_driver --complete` — pass; `cpu-static-check.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484D-165-3__motor_vehicle_driver --complete --require-delivery-ready` — fails at partial/missing packages; `cpu-strict-check.log`.

## Next CPU work

1. Finish the pinned Native output lifecycle: write source-bound `result.json`, `capture-seal.json` with closure ordering and world restoration, then test Native output validation. Add required semantic stage proposals and selected-requirement mappings; adapt `finalize_original.py` to the pinned process-saved `--attempt/--output` interface.
2. Provide each exact case a source-hashed diagnostic recipe and positive/negative `runtime.py compatibility`, then CPU-test `runtime.py process-saved` and independent full video decoding. The six refreshed exact offline checks pass. Author and test a source-preserving camera-station fallback where physical risk justifies it; keep comparison variables fixed.
3. Review original law and referenced timing text again, resolve site documentation and implementation gaps, then rerun the exact strict gate. Physical CARLA visibility, lamp color/readability and capture quality remain later GPU checks.

No input, runtime, batch or shared files were edited; no Git command was run.
