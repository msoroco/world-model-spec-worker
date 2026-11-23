# testing__C229398__NRS-484D-165-3__motor_vehicle_driver

Status: partial. Exact static check passes; strict delivery gate fails on partial status. No accepted recordings are available for reuse.

## Coverage and source review

The exact NRS 484D.165(3) text incorporates subsection (1) lamp properties and references the times in NRS 484D.100(1). The source-hashed witness is conditional: C229398 curb parking may intersect traveled roadway or adjacent shoulder, but site, timing, illumination and visibility facts must be measured. `case-plan.json` maps six exact cases: `dark_lamps_on`, `dark_lamps_off`, `dark_attended`, `dark_traveled`, `sufficient_light`, and `outside_referenced_time`. It has five controlled comparisons: lamp activation, attendance, placement, 1,000-foot revelation precondition and referenced time. All six are planned new captures; there are zero frozen accepted recordings. The 1,000 and 500 foot distances are statutory observation stations, not invented photometric cutoffs.

## Implemented CPU construction and proof

`execution-manifest.json` binds six exact inline bundles under `construction-*.json`; each materializes its own `runner.py`, source checker, exact `config.json` and focused bundle test. All six exact `runtime.py offline` checks pass (`proof-*.log`), with generated trees kept under `.runtime-work/`. The Native runner currently requires a source site packet and explicitly rejects capture until the four-camera acquisition is implemented. `finalize_original.py` joins a saved site packet, 900-frame original history, frame map, four camera seals and case identity; its positive/negative test rejects a stale original history. `parked_lamps.py` verifies source-sealed highway, curb boundaries, traffic side, referenced time, lamp installation, map identity and 1,000/500 foot station locations before Native spawn. Its lazy `construct` spawns a vehicle at a source-specified shoulder or traveled transform, applies the parking brake, sets lamps and reads back Native lamp state. Its `measure` requires 900 contiguous original frames at 20 Hz with parking, lamp, light, time, station and source-camera records. It records unknown photometric observations without assigning a legal verdict. `audit_saved_capture` independently checks sealed original frame-map and four named camera sources; `audit_comparison` checks exact members, original evidence, site identity and declared differences.

Eleven focused CPU tests pass, including Native fake construction of both placements, all six original-frame variants, negative missing source, lamp state, frame-gap and camera cases, and both lamp/time comparison isolation checks. Synthetic receipts are software fixtures only.

## Exact commands and logs

- `.venv-cpu/bin/python runtime.py preflight` — pass; `cpu-preflight.log`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229398__NRS-484D-165-3__motor_vehicle_driver/tests -v` — 11 tests pass; `cpu-tests.log`.
- Six case-specific `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C229398__NRS-484D-165-3__motor_vehicle_driver/execution-manifest.json --case EXACT_CASE --output .runtime-work/c229398-offline-v3-CASE --python ABSOLUTE_VENV_PYTHON` checks — all pass; `proof-*.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484D-165-3__motor_vehicle_driver --complete` — pass; `cpu-static-check.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484D-165-3__motor_vehicle_driver --complete --require-delivery-ready` — fails at partial/missing packages; `cpu-strict-check.log`.

## Next CPU work

1. Finish Native capture in `runner.py`: source site packet, four actual synchronized cameras, 900 original frames, frame map and sealed packet. Add required semantic stage proposals and selected-requirement mappings; integrate `finalize_original.py` with the pinned process-saved interface.
2. Provide each exact case a source-hashed diagnostic recipe and positive/negative `runtime.py compatibility`, then CPU-test `runtime.py process-saved` and independent video decoding. The six exact offline checks already pass. Test any physical-risk fallback construction before listing it.
3. Review original law and referenced timing text again, resolve site documentation and implementation gaps, then rerun the exact strict gate. Physical CARLA visibility, lamp color/readability and capture quality remain later GPU checks.

No input, runtime, batch or shared files were edited; no Git command was run.
