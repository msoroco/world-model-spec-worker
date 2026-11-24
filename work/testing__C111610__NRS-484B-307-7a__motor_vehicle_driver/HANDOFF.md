# testing__C111610__NRS-484B-307-7a__motor_vehicle_driver

Status: partial executable construction. Five cases are planned; no recording has been accepted.

Exact law: NRS 484B.307(7)(a) — Where the signal is a flashing yellow turn arrow, displayed alone or in combination with another signal: Vehicular traffic facing the signal is permitted to cautiously enter the intersection only to make the movement indicated by the arrow signal, or other such movement as is permitted by other signal indications displayed at the same time. Such vehicular traffic must yield the right-of-way to pedestrians lawfully within the intersection or an adjacent crosswalk and yield the right-of-way to other traffic lawfully within the intersection.
Assigned branch(es): Pedestrian yield duty.
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-307-7a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

The frozen evidence inventory contains zero accepted recordings. Five exact planned cases now cover arrow-only left turn without another participant, person afoot in adjacent crosswalk, person afoot within intersection, other motor traffic within intersection, and an additional movement allowed by a concurrent indication. `case-plan.json` names four controlled comparisons and exact evidence gaps. The one frozen source topic is mapped to these cases. Presence in a surveyed region is measured; lawful presence, cautious entry, right of way and compliance remain external legal/context questions with no numeric cutoffs.

`native_arrow.py` verifies hashed original map, signal, route and crosswalk sources; checks the surveyed turn and signal facing; lazily spawns ego and a distinct participant with cleanup on spawn failure; and measures frame ordered original arrow exhibition, movement, pedestrian/vehicle classification and polygon occupancy. `turn_control.py` provides conservative approach, hold and turn control. `comparison_audit.py` rejects absent frame histories, changed fixed conditions, incorrect region/class, missing arrow exhibition and unsupported legal verdicts. The Native signal head alone cannot establish a flashing arrow; an externally sourced original aspect packet is an explicit acquisition dependency, still to be wired into the exact runner.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 7 tests; retained `cpu-tests.log` has the SHA in `result.json`. The exact strict assignment gate was rerun and reaches the expected `Preparation acceptance failed: partial/missing packages remain`; retained `cpu-strict-check.log` proves this checkpoint is not ready.

Next CPU work: bind a concrete Native map and official arrow signal source to a runner/config/manifest; implement original aspect acquisition, case-specific finalizer, capture and semantic proposals, per-case offline and source-bound positive/negative compatibility, saved-only processing and independent delivery audit; then rerun exact strict gate. Actual CARLA motion, display realization and camera coverage remain later physical checks. Do not mark ready until the strict CPU gate passes.

## 2026-11-24 original aspect acquisition checkpoint

`aspect_capture.py` now records one injected Native display-adapter packet per 20 Hz tick for 900 ticks, binds official head, facing approach, arrow color/direction, Native head readback, source identity, concurrent indication inventory, contiguous frames and timestamps, and requires observed on/off transitions. It seals the original source and receipt under the attempt directory. The adapter callback must read the actual display or controller; CARLA's coarse traffic-light state is not assumed to identify a flashing arrow. `saved_aspect.py` independently rejects missing, tampered or escaped sources, diagnostic input in delivery mode, and an event history that invents an illuminated arrow during an observed off phase. These modules do not assert physical realization or a legal judgment.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 12 tests. `cpu-tests.log` SHA256 is `6dcd53a0251d5396483675412c1f59f60897ea3f163a321fc1c9d66471bddb2c`. Exact scoped `worker_check.py --assignment testing__C111610__NRS-484B-307-7a__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 is `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`. Exact scoped `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain`; `cpu-strict-check.log` SHA256 is `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

`native_arrow.measure_original` and `comparison_audit.audit` now require observed on/off transitions, and the comparison also holds original arrow timing fixed. Remaining CPU integration: connect the adapter to a concrete surveyed head and exact runner; join the sealed source in the case finalizer and comparison audit; complete semantic proposals, exact case bundles and manifest, source-bound compatibility and delivery audits, and canonical local integration proofs. Physical display and intersection realization remain later checks.

## 2026-11-24 synchronized Native event checkpoint

`event_capture.py` now accepts one callback per Native tick that returns the original display readback and actor-event packet together. Before writing either original source, it checks all 900 frame identities, 20 Hz timestamps, official head and facing approach, concurrent indications, arrow on/off agreement, actor event presence, and flashing transitions. It seals `arrow-aspect-original.json`, `arrow-aspect-receipt.json`, and `arrow-events-original.json`, then reopens the saved pair with `saved_aspect.join_event_history`. The callback is an interface for the later concrete CARLA runner, not a fabricated display source or physical acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 14 tests; `cpu-tests.log` SHA256 is `fca0a38c6da130c0b10d9f51f57fb56c9071892ae890c15830af87fc1b41234d`. New tests check exactly one tick callback per frame, saved replay, tamper rejection, no overwrite, and rejection of a divergent display packet before source files are written. The remaining CPU integration and exact runner/config/manifest, finalizer, per-case proofs, semantic proposals and independent delivery audit remain unfinished; this assignment stays partial.

The exact scoped static check exited 0 (`cpu-static-check.log`, SHA256 `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`). The exact scoped strict check exited 1 solely because this package remains partial (`cpu-strict-check.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). All 15 returned files are UTF-8 text under 2 MiB with no trailing whitespace, conflict markers or caches.
