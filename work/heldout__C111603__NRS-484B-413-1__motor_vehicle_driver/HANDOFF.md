# heldout__C111603__NRS-484B-413-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-413-1, cell: C111603, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/assignment.json` (42cc01f69660afb23a9167a02ab7151ddd33a1fee873db9920a705453a389cd8).

Exact law text: A driver shall not turn a vehicle from a direct course upon a highway unless and until such movement can be made with reasonable safety, and then only after giving a clearly audible signal by sounding the horn if any pedestrian may be affected by such movement and after giving an appropriate signal if any other vehicle may be affected by such movement.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111603__NRS-484B-413-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- turn from direct course with measured physical clearance and reasonable-safety judgment retained
- pedestrian may be affected: audible horn signal versus none, with other conditions fixed
- other vehicle may be affected: appropriate signal versus none, with other conditions fixed
- both pedestrian and vehicle may be affected: both signals required

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 original signal/audio checkpoint

`turn_signal_measurement.py` now joins 20 Hz original ego yaw, Native turn-indicator readback, and raw listener audio samples at a separately sourced pedestrian listener. It requires source-cited booleans for whether a pedestrian or other vehicle may be affected, reports turn onset, pre-turn indicator frames and pre-turn listener RMS, and leaves reasonable safety, clearly audible and appropriate-signal judgments null. It rejects command-only audio, a mismatched listener, missing affected-participant citation and broken original frame joins. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/tests -v` passes three CPU tests (`cpu-tests.log`); the scoped partial static gate passes (`worker-check.log`). These are source-shaped software checks, not proof that a CARLA horn exists or is audible to a real pedestrian.

`case-plan.json` now plans controlled reasonable-safety clearance, pedestrian horn/no-horn, vehicle indicator/no-indicator, hand-signal alternative, and both-affected conjunction comparisons. There are no accepted recordings in the frozen inventory. Each exact case still needs a Native construction and the actual signal/audio acquisition mechanism. In particular, a controller command alone cannot establish a clearly audible horn, and the pinned adapter does not gain hand-signal evidence from a flag. Keep this package **partial** while implementing those CPU paths, four source cameras, finalizer, three fallbacks per case, offline and positive/negative compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Then run the strict scoped gate. Physical sound, visible signals and motion remain for later original-source review.

The source measurement now rejects nonfinite original yaw, frame time and listener audio samples before computing turn onset or RMS. A NaN sample previously escaped the amplitude range check and could contaminate the reported observation. Four CPU tests pass (`cpu-tests.log`, SHA256 `8fb10b98797ea414e01fcd7d78af9c43e1ba189c7dd7c61fbe30c311ccc027a9`). The next CPU construction remains an actual original-source signal and listener-audio acquisition path; no physical or legal audibility is inferred from this fixture.

## 2026-11-11 participant clearance checkpoint

`turn_signal_measurement.py` now requires `participant_bodies.jsonl` joined at every 20 Hz ego frame and an independently cited `participant_geometry_source` plus explicit participant IDs and types in `affected_participants.json`. The ego motion rows must carry original `x_m`, `y_m`, and positive `body_radius_m`; each participant body row carries the same geometry. The output hashes all four original sources and reports per-participant minimum sampled surface gap, gap at measured turn onset, and a constant-velocity closest-approach proxy at that onset. Signed gap can be negative for overlap. The proxy is a kinematic description without a legal reasonable-safety cutoff, and the context booleans remain separately sourced claims about who may be affected. These source packets still need Native acquisition code and saved-processing integration; the unit fixture cannot prove real clearance or audio.

`.venv-cpu/bin/python runtime.py preflight` passed (`preflight.log`, SHA256 `f34c8c666500214ed53e2753a7a988dd84ef1dc88e6105093776dd854c7db554`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/tests -v` passed six tests (`cpu-tests.log`, SHA256 `4db3ba1b2bde181814aa150bebc4ada542ee1b5a59c419d9ef3a6d4f3913ef09`). New negative tests reject a missing or frame-misaligned participant source and invalid body geometry or absent geometry provenance.

Next CPU work: implement Native acquisition of original participant transforms/bounds, signal readback, and actual listener audio; connect this measurement to a selected exact case's saved finalizer; author the four-camera capture and execution bundle; run that case's offline, compatibility positive/negative, and saved-processing proofs. Then expand linked cases, fallback candidates, proposals, and independent audits. Keep `result.json` partial until the scoped strict gate passes.

The frame join now also rejects skipped original frame numbers despite regular timestamps; seven tests pass (`cpu-tests.log`, SHA256 `f2784ed3300df63bf97da977b4fac52dd12bbaf7d20d649ecc50908222ee7cca`). The scoped partial check `.venv-cpu/bin/python worker_check.py --assignment heldout__C111603__NRS-484B-413-1__motor_vehicle_driver --complete` passes (`worker-check.log`). The scoped `--require-delivery-ready` check fails because `result.json` remains partial (`strict-gate.log`); no ready claim is made.
