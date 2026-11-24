# testing__C158196__NRS-484B-307-6a__motor_vehicle_driver

Status: **partial**. Exact static check passes; exact strict delivery gate rejects the partial package. Do not promote to ready.

## Source and coverage

NRS 484B.307(6)(a) governs vehicular traffic facing a steady yellow signal alone. It warns that the related green movement is terminating or a steady red will follow, and bars intersection entry when red is exhibited. This package retains the original unresolved meaning of the entry reference and “immediately thereafter”; 20 Hz brackets are measured evidence, not invented legal cutoffs. Cell C158196 is a one-way-to-two-way intersection with a vehicular traffic light and motor-vehicle driver. The seven frozen accepted recording IDs and their metadata/source hashes are inventoried in `case-plan.json.evidence_review`; the original trace/video is absent, so authored descriptions and membership do not establish physical coverage.

`case-plan.json` now lists the seven exact case identities `enters_yellow`, `enters_red`, `inside_on_red`, `red_other_route`, `yellow_red`, `stops_red`, and `yellow_non_alone`, and six controlled comparisons `yellow_entry`, `already_inside`, `red_entry`, `facing_governance`, `green_termination`, and `steady_yellow_alone`. Every case names its gap, physical risk, required source classes, and evidence reuse candidate. The sole source topic `exact-text` and all applicable clause elements are in requirement dispositions. Judgment range inventory for this exact law and actor is empty.

## Implemented CPU work

- `construction.py` is a lazy, source-gated adapter-facing scene builder. It checks surveyed map/device/route hashes, route direction sequence, official vehicular head facing the selected route, 20 Hz / 900-frame / four-camera profile; then invokes world setup, ego spawn, signal program, route controller, and camera attach through a supplied adapter. This is an executable facade with fake-adapter tests, **not** a completed CARLA binding or a physical signal proof.
- `signal_measurement.py` requires original 20 Hz frame identities, Native source bindings, surveyed intersection polygon, selected official vehicle head readback and route binding. It measures green→yellow→red transitions and adjacent-frame ego-front entry brackets. A phase-straddling entry remains unresolved. It does not decide legality.
- `comparison_audit.py` independently checks sealed source identity, 900 frames, video/pixel/physical evidence, fixed scene conditions, and a realized declared difference. It rejects missing evidence and changed fixed conditions. It is a CPU component, not a completed delivery receipt.
- `tests/test_signal_measurement.py` exercises all seven construction profiles, a 900-frame measurement fixture, positive phase/entry measurements, and negative missing-source, timing, signal and comparison cases. Synthetic fixtures do not establish actual motion or visible signal heads.

## Checks

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/tests -v`: exit 0; `cpu-tests.log` SHA256 f99afbc481d9e383344daed37c95ba090ba91909079009963cf95375613fe5e6.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --complete`: exit 0; `static-check.log` SHA256 154d605aa856e5dcc8e4c76775342706ed575ded07bfa80b9d9f46cb68d2062d.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `Preparation acceptance failed: partial/missing packages remain`; `strict-check.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## Next CPU work

1. Bind `construction.py` to the pinned Native CARLA entry points, source-readback official device and surveyed intersection geometry; implement a controller that realizes each phase/entry case without teleporting. Read back and restore world settings. Reconcile any unsupported companion-indication case with actual device capability.
2. Implement the exact case finalizer and per-case 900-frame diagnostic recipes. Run exact offline and positive/negative compatibility proof for each exact bundle, using `.runtime-work/` for generated media. Prove 20 Hz original source packet joins and no source substitution.
3. Author and validate all canonical semantic stage proposals, complete execution manifest, saved-only postprocessing, physical completion and independent delivery audits, and source-bound positive/negative proofs. Add one or two tested risk-triggered fallback constructions only where needed.
4. Review available original accepted traces/videos when accessible through the frozen source inventory; retain uncertainty where absent. Repeat exact static and strict gates after each completion step. Actual CARLA motion, visibility, camera coverage and acceptance remain later physical checks.

## 2026-11-23 companion signal and entry-state checkpoint

- `construction.py` requires a separate source-bound official companion device for exact `yellow_non_alone`, binds its Native actor, checks facing route and source hash, and programs it active during yellow. The ordinary selected head remains the route-facing vehicular device. SHA-256 `3d80103244b6a15df544979eec8ac7241dc05472e25d8fa6736e2229f69343d0`. This is an adapter contract with fake-actor proof; physical lamp visibility still requires Native capture.
- `signal_measurement.py` now distinguishes an ego already inside at first original frame from one that never enters; the former no longer silently reports `no_entry`. A `yellow_non_alone` profile admits only a source-read companion lamp and records its original frames; steady-yellow-alone cases continue to reject companions and flashing. Missing or invalid companion readback is rejected. Legal judgment remains unresolved. SHA-256 `d3808c71a2d5ca44f73cc71b5d73ea9e427f35afde3e147489477b296a74cf24`.
- Pinned preflight passed; 14 focused tests passed (`cpu-tests.log` SHA-256 `0f62d6e66c43c5e71261e2c6a8aa84558c2dff8a81823f5cc3acb2455310dd44`), including companion positive/negative, initially-inside, 900-frame and source rejections. Scoped static complete passed (`static-check.log` SHA-256 `154d605aa856e5dcc8e4c76775342706ed575ded07bfa80b9d9f46cb68d2062d`).
- Exact scoped strict gate exited 1 at partial-package acceptance; `strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. Status remains partial. Next CPU work: bind the real Native adapter and 900-frame case-specific bundles; source-review seven accepted traces/videos; implement exact diagnostic, semantic proposals, saved finalization and independent delivery audit; prove offline and positive/negative compatibility for every exact case and justified fallback.
