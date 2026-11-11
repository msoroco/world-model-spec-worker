# NRS 484B.127(1), C101303: partial CPU checkpoint

The exact law requires the driver to avoid following another vehicle more closely than is reasonable and prudent, with due regard for both speeds, traffic, and highway condition. That standard has no numeric cutoff in the supplied text. The assigned cell is a hill crest with a lane change and another vehicle; the selected branch is following before the lane change.

## Preserved accepted evidence

`case-plan.json` reviews all eight inventory records from `inputs/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/evidence.json`. The frozen metadata identifies accepted `base`, `closer`, `faster_ego`, `slower_lead`, `lead_brakes`, `wet_surface`, `following_ends`, and `queued_traffic` cases, each with 900 frames and a decoder-pass report. `evidence_audit.py` checks every inventory hash and identity against its metadata. The supplied `review-context/review.json` names the intended variants, but the exported files do not contain the original traces or videos. Thus their measured distances, speeds, conditions, relation intervals and physical visibility remain unknown. No new recording is proposed yet, and no case is claimed as equivalent or legally sufficient.

## Exact CPU work still required

1. Review the retained trace, video and delivery audit for each of the eight case IDs listed in `case-plan.json`; bind actual observed following intervals, body gaps, both speeds, traffic and surface state, and lane-change timing to source hashes. Decide which requirements have source-backed reuse and which gaps need new cases. Do not replay an accepted original.
2. Finish the full branch matrix for the exact law, including controlled comparisons with fixed conditions and measured deliberate differences. Update this assignment's `case-plan.json` and the lead-owned `work/_shared/branch-coverage.json` and review. Do not invent a legal distance or time threshold.
3. For uncovered requirements, implement exact constructions, controllers, four-camera capture, measurement/finalization, three distinct fallback constructions per selected case as requested by `AGENT_PROMPT.md`, semantic proposals, saved-only processing and independent delivery/comparison audits. Run exact offline and positive/negative compatibility checks for each construction and fallback. Bind current hashes after changes.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C101303__NRS-484B-127-1__motor_vehicle_driver --complete --require-delivery-ready`, then the complete-batch strict gate after all assignments are prepared.

## Environment and checks

- `python3.11 -m unittest discover -s tests` passed all six repository baseline tests.
- `python3.11 -m unittest discover -s work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/tests -v` passed; see `cpu-tests.log` and the hash in `result.json`.
- `.venv-cpu/bin/python runtime.py preflight` now passes with the pinned CPU requirements, ffmpeg, ffprobe and lake. The earlier `preflight.log` and `pip-install.log` are historical failed attempts; their dependency diagnosis is resolved.

This is a partial checkpoint. Missing implementation is unfinished CPU work, not a GPU blocker. Physical realization and any legal judgment remain unverified.
