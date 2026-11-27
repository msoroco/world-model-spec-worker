# NRS 484B.400(1) at C399695

Status: partial CPU construction. The frozen evidence inventory has zero accepted recordings. The same-cell NRS 484B.223(4)(a) package concerns lane purpose; it does not prove both approach and turn lane position under this law.

The exact text requires an identified driver intending a right turn, both the approach and the turn from a qualifying NRS 484B.223(4) right-turn lane if one exists, or from the extreme right lane otherwise. `case-plan.json` selects five exact cases. `approach_lane_position` isolates the approach interval; `turn_lane_position` isolates the turn interval; `both_intervals_position` samples the combined divergence; `conditional_lane_design` compares a source-reviewed qualifying lane to the extreme-right alternative. The latter needs a distinct original site lane-design packet; its feasibility in the frozen cell remains for local map review. No numeric lane-entry deadline or legal lateral cutoff is invented. `judgment_ranges.json` contains zero ranges for this law.

`turn_position.py` measures original joined road/lane IDs, body pose, driver identity, approach and turn phase ordering, connected departure, and independently sourced right-turn intention. It rejects missing NRS 484B.223(4) qualification, source gaps, nonmonotone frames, driver mismatch and wrong road topology. `native_turn_construction.py` chooses exact source-surveyed Native lane trajectories and rejects unsourced lane changes or wrong conditional lane design. These are software preparation only; no actual site geometry, CARLA path, video or legal outcome is asserted.

## Proven CPU checks

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C399695__NRS-484B-400-1__motor_vehicle_driver -p 'test_*.py' -v`: six focused tests passed; retained `cpu-turn-position-tests.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C399695__NRS-484B-400-1__motor_vehicle_driver --complete`: static partial check passed.
- Exact `--complete --require-delivery-ready` fails while result remains partial, as intended.

## Remaining CPU work

Implement the executable Native capture/controller and saved finalizer using this source-gated contract. Bind each exact construction and current-runtime offline, positive/negative compatibility and saved-only receipts. Add canonical semantic proposals, physical/lifecycle checks, independent delivery and comparison audits, justified fallback candidates, exact manifest and GPU queue proposal. Then run the exact strict assignment gate and repair every failure. Actual CARLA motion, lane realization, video coverage and local acceptance remain later physical checks; they are not a CPU blocker.
