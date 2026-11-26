# C376646 NRS 484B.250(4) motor vehicle handoff

Status: delivery prepared. The exact scoped strict CPU gate passed with exit 0; Native physical and legal acceptance remain pending.

## Exact construction

Six source-gated cases exercise an installed, uncovered, fully inoperative governing signal at intersection entry; the marked stop line, no-line near-side crosswalk and neither-present nearest-view hierarchy; prior-stopped, within-intersection and no-priority other vehicles; and a late stop. Three controlled comparisons test priority, stop-reference hierarchy and stop position. `native_signal.py` requires reviewed source hashes, connected routes and Native readback. `runner.py` defers CARLA import until source checks pass. `native_capture.py` captures 900 synchronized 20 Hz ego/other histories and four original RGB streams, then restores world settings. `native_output_bridge.py` seals the original packets for the pinned runtime. `analysis.py` measures saved originals and leaves cautious proceeding unresolved without a fabricated threshold.

## CPU proof results

- Runtime verify and preflight passed.
- Nine focused assignment tests passed; `cpu-tests.log` SHA256 `a44ef86e09fd23a3307483a24012e068395c877abccac8297baa982b5b181729`.
- Six primary and six fallback exact-case offline checks passed.
- Six primary and six fallback positive/negative compatibility runs passed, including selected measurement contracts and full diagnostic video decode.
- Six selected saved-only positive and missing-source probes passed.
- Each case passed synthetic complete, incomplete and missing-evidence physical outcomes plus Native lifecycle ordering. These are diagnostic protocol proofs, not physical acceptance.
- Six independent positive/negative delivery audits and three controlled comparison audits passed on diagnostic packets.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready`: exit 0; `strict.log` SHA256 `61f61d4613193e63b7817d3e4fd26b167d06c4bf64fc9d1ac5e74864db32f2fe`.

## Stable handoff

- Execution manifest SHA256 `4377646c536729bdce43065e27e00ac53c15463d48f812f38365e748aacbfaa4`.
- Queue proposal SHA256 `63915f65ff4650afc4a2acb727aa3c34228c3473a2853086190e6f817a4f3307`. Parent integrates the shared queue.
- Returned work tree has 282 UTF-8 files, all at or below 2 MiB, with clean whitespace and EOF.
- Frozen evidence inventory has zero accepted recordings. Local delivery still needs a source-reviewed official signal/site/operator packet, original CARLA motion and pixels, independent physical completion and legal review of cautious proceeding.
