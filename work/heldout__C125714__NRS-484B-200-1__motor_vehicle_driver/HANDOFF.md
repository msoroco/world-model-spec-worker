# heldout__C125714__NRS-484B-200-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-200-1, cell: C125714, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C125714__NRS-484B-200-1__motor_vehicle_driver/assignment.json` (c8ddf30399cb5d1fc97236ca21271f82a126c632ddf16a819a853f952434c268).

Exact law text: Upon all highways of sufficient width a vehicle must be driven upon the right half of the highway, except as follows: (a) When overtaking and passing another vehicle proceeding in the same direction under the laws governing such movements; (b) When the right half of the highway is closed to traffic; (c) Upon a highway divided into three lanes for traffic under the laws applicable thereon; (d) Upon a highway designated and posted for one-way traffic; or (e) When the highway is not of sufficient width.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C125714__NRS-484B-200-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C125714__NRS-484B-200-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- right-half driving baseline on sufficient-width two-way highway
- overtaking/passing same-direction exception under governing passing laws
- right-half closure exception
- three-lane highway exception under applicable lane laws
- designated and posted one-way exception
- insufficient-width exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 construction checkpoint

The frozen evidence inventory has zero recordings. Eight exact case intents and seven controlled comparisons now cover the continuous baseline and all five express exceptions in `case-plan.json`; all are `planned_unimplemented`. No accepted reuse is asserted.

`directed_geometry.py` derives a direction-aware center boundary from joined, opposite-direction Native lane waypoints, rejects a separated median and wrong-way or unjoined lane, and reads four bottom body corners from the original actor bounding box. `roadway_source_capture.py` writes new, original 20 Hz rows with frame and actor identity. `right_half_measurement.py` reads those rows and measures full-body right-half occupancy, crossing and road width without inferring sufficient width or any exception. These modules are acquisition and measurement work; they are not an executable route/controller or delivery capture. The median-opening cell may require explicit map geometry beyond the directly joined lane helper.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C125714__NRS-484B-200-1__motor_vehicle_driver/tests -v` exited 0, nine tests; `cpu-tests.log` SHA-256 8bcdeb19ce5d7cfaa10335d27aa67a60f1f57391c39ae9db6f1882b636fd77e6. Scoped static and strict gates are rerun in `worker-check.log` and `strict-gate.log`.

Next CPU work: implement route and controller for the selected median-opening cell, four synchronized cameras, exact construction bundle and three fallbacks only for documented physical risk; bind case-specific saved finalizer and positive/negative compatibility; expand eight cases and comparisons; add semantic proposals and independent delivery/comparison audits. Select legal sufficient-width and exception dispositions only with separate original context; no cutoff is assumed here.

## 2026-11-11 baseline Native probe

`native_right_half_probe.py` now selects a joined two-way route, applies feedback control, captures original 20 Hz directed body footprints and four synchronized lossless RGB streams, and restores world settings with readback. `probe-config.json` flags it as construction-only; `construction-probe.json` inlines the exact code and tests. `runtime.py offline` passed without starting simulation (`probe-offline.log`, SHA-256 4258098cd392b650052af958167da99f2845ac61253a455ee9c4e516e74811b8). The latest local unit suite has 13 passing tests (`cpu-tests.log`, SHA-256 b40039631fabea08101872a1d41f4fc713b159b0fc0986b219aeb3220bb8e5e5). `probe-proof.json` binds these hashes. No actual CARLA motion or median-opening realization is claimed.

The route selector rejects a separated median; physical scene selection for the fixed median-opening cell still needs a source-backed route. No Native attempt is sealed, and there is no saved-only converter, renderer or independent delivery audit. Complete these CPU tasks and all eight exact cases before changing partial status.

## 2026-11-11 saved-only join update

`right_half_finalizer.py` reads saved `config.json`, `video_frames.jsonl`, `trace.jsonl` and `directed_roadway_footprints.jsonl`, checks exact frame/time joins and returns source-hashed right-half observations. `native_right_half_probe.py` now emits the same trace and frame-map sources through pinned `PipelineCapture` and `FrameMap`. Positive, missing-source and stale-frame CPU tests pass. The 15-test local suite SHA-256 is 8622939e03b6cbbd3e27e39c46a99565b840eb16d4a75bbe73d7c5c8f3c2c32c. The rebuilt inline probe passed exact `runtime.py offline` (log SHA-256 40a9f6891692f087dcf0d86941261df9e3b34a70b034f2a0f45fdba4fea19101). `probe-proof.json` binds the current construction SHA. This is saved analysis only; it does not yet write a canonical result or pass package compatibility.

`right_half_finalizer.py` now builds a canonical Native result shape with derived `right_half_offset_m.jsonl` from original directed footprints only. The CPU fixture passes pinned `native_output.validate_result`, rejects missing originals and stale trace joins. The probe config now declares four named cameras and the source measurement description. Rebuilt exact offline probe passes, log SHA-256 4e414db81f7c776a6885c9d3c3752d3d15289110548166a4b639ea2796381149; 15 local tests pass, log SHA-256 620503e6ed9def56d742ade6e8b470d0f97402fefaf1a406f8020cfb5f4792f4. Full runtime compatibility and case delivery remain open.

The saved right-half analyzer now accepts all eight planned case IDs as measurement-only input while leaving every legal exception judgment null. The source acquisition for one-way, three-lane and narrow-width scenes remains unimplemented. Latest local suite: 16 passed, SHA-256 98008ec52f92d67478a336c6079aaaf5b80c93cf9099b3a059765138718de032; latest exact baseline offline probe SHA-256 fd9041be9c6edd315a6252bcb2d105cd3e7fb2824887f8c5db11ef186ab0742c.

The saved finalizer now requires the exact assignment-prefixed case ID for each of eight planned cases. Rebuilt source hash and offline proof are in `probe-proof.json`; exact offline exited 0, `probe-offline.log` SHA-256 d1f93a4b6b24b690b76cc2de8100ee4b9dc37bcbc272823b5b5fbda12d35445b. Sixteen unit tests pass, log SHA-256 a16770952c6d7c93b7254a7a12b4952f7e0b1778554fc0b3850a28365bde7322.

The baseline route now selects only eastward travel for the exact east case; a westbound map route is rejected in the source-shaped test. Probe config and runner bind `travel_direction=east`. Rebuilt exact offline proof passes, log SHA-256 e2c309cd3f93aebf4086c48af20c13e6979c8971c0d364a20fc9a62a0ce45d3a; 17 unit tests pass, log SHA-256 679d61fd335f8302cde2a70fee35fa88fe4315a5d6f5482c3c5d851924d3a8af.
