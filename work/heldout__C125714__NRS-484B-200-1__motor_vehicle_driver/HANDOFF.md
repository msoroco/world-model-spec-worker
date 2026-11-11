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
