# C230286 exact school-bus speed delivery handoff

Status: ready for exact GPU delivery preparation. The scoped strict CPU gate passed on 2026-11-26. Original Native capture, independent pixel review and legal interpretation remain pending on GPU.

Exact assignment: `testing__C230286__NRS-484B-360-1__school_bus_driver`. NRS 484B.360(1) limits a school bus to 55 mph when transporting pupils to or from school. Four cases request 54, 55 and 56 mph during a sourced pupil trip and 56 mph outside the active trip interval. Two controlled comparisons cover the speed boundary and transport phase. Commanded speeds are construction targets, not measured legal findings.

The Native runner requires separately hashed map, 900-metre drivable route, sidewalk relation, school-bus qualifying definition branch and exclusion dispositions, bus and driver identity, trip purpose, pupil presence, pupil count, and bus pose. It captures 900 consecutive 20 Hz Native frames, bus velocity and pose, source-joined active pupil transport, and four lossless camera streams. The saved-only analyzer verifies original source hashes and frame joins. The independent delivery audit requires a full decode, bus and sidewalk pixel review, source-measured physical completion and leaves legal verdict null.

CPU proof scope: four selected offline passes with simulation not started; four selected positive/negative compatibility runs through saved analysis, Native validation, Lean Core and four-camera rendering; four recorded-only saved replays; four source-shaped physical complete/incomplete/missing and lifecycle proofs; four current-hash controller-gain fallbacks with offline and compatibility proofs; four positive/negative independent delivery protocol proofs; two positive/negative comparison audits. Synthetic diagnostics do not assert original capture quality, physical acceptance or school-bus legal status.

- Execution manifest SHA256: `a7050a4ff4c5c18932c07852c7e562f4a46eb1264240a66fd72d2598970a038b`
- GPU proposal SHA256: `3afb1c6ae5c7d936dcd5604b8c2732200bdfac27d372e152a405a9a53111bbe3`
- Exact strict command: `.venv-cpu/bin/python worker_check.py --assignment testing__C230286__NRS-484B-360-1__school_bus_driver --complete --require-delivery-ready`
- Exact strict result: exit 0, `static_checks_passed=true` (see `strict.log`).

The lead may independently rerun the exact strict command and integrate `gpu-queue-proposal.json`. The first queued execute command is in `result.json`. Preserve the source-gated reviewed site and trip packet requirement during GPU delivery.
