# C130282 rotary traffic island handoff

Status: `ready` for source-gated CPU delivery preparation. The exact assignment gate passed on 2026-11-26. This is not physical or legal acceptance.

The four selected exact cases are `inner_right`, `inner_left`, `outer_right`, and `outer_left`; the three controlled comparisons are `inner_side`, `outer_side`, and `right_lane_choice`. The frozen NRS 484B.220(2) text controls. A multilane roundabout label does not establish a qualifying rotary traffic island. No accepted original recording is listed in the frozen inventory.

The selected Native bundle requires an independently reviewed and SHA-sealed original OpenDRIVE map, physical rotary-island polygon and identity source, connected inner/outer circulation lanes and case-specific entry/exit routes, motor vehicle and driver source, source-selected spawn, and four camera poses. Left-side requests additionally require reviewed physical route and clearance. The Native runner aborts on a missing or changed source. It records original 20 Hz live lane, heading, center, eight-vertex vehicle body, and four synchronized cameras for 900 frames. Saved analysis reports sampled island-side sign, body overlap and lane identity. Between-frame continuity, physical feasibility, legal side status and actual camera visibility remain unresolved until original capture and review.

CPU proofs passed: eight primary/fallback offline checks; eight pinned-runtime compatibility checks with selected measurements and missing-map negatives; four three-outcome physical/lifecycle receipts; four independent delivery positive/missing-map pairs; eight saved-only positive/missing-map checks; three comparison audits; nine local tests. The diagnostic geometry and videos are explicitly synthetic and never stand in for original source. All four selected cases have a bounded throttle fallback on the same reviewed route. The assignment-scoped GPU queue proposal contains four exact jobs and three comparison commands; lead integrates the shared queue.

Exact gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C130282__NRS-484B-220-2__motor_vehicle_driver --complete --require-delivery-ready` exited 0. The result is in `strict-gate.log`.

Stable SHA-256:

- `case-plan.json`: `fe35d98ef315b8eaf34908f08b3502c6287e82d38b795f36d9c32038fc518068`
- `execution-manifest.json`: `ce0047d7f343da822c5ba9549c3d7d062c497cc2c390bfe997cbabcecf5be4e1`
- `gpu-queue-proposal.json`: `64732913ceeb7a729abf8ee7c4ee5f1411fef228e6cf53aaab712e159ac04663`
- `result.json`: `1881c21727b7c472eb15dac7601ab0b522d734be77d77c81453ff167bba58336`
- `strict-gate.log`: `9c397dce405df8f33da933604a810fd3dcb0d24c6b4959f9f961453cfa64b224`

All returned files under this assignment are UTF-8, at most 1,219,264 bytes, with clean whitespace and EOF. Scratch and generated attempts are under `.runtime-work/c130282/`.
