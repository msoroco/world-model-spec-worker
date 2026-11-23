# testing__C10301__NRS-484B-600-1e__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.600(1)(e) — It is unlawful for any person to drive or operate a vehicle of any kind or character at: In any event, a rate of speed greater than 80 miles per hour.
Assigned branch(es): Unconditional restriction during qualifying operation..
Cell: C10301 (alley, travel, access_aisle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 3. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU boundary construction checkpoint

The exact NRS 484B.600(1)(e) restriction is greater than 80 mph. `case-plan.json` now records the three exact `__below`, `__equal`, and `__above` case IDs and controlled `strict_rate_boundary` comparison. The middle case ID follows the frozen accepted membership name; its intended 80 mph target follows the frozen accepted review, but does not claim observed 80 mph equality. Frozen review context reports sampled maxima of 74.95, 79.73, and 80.70 mph for the prior accepted recordings. Those are summary claims only: the original trace/video is absent here, between-sample peaks are unknown, and the 79.73 mph result does not demonstrate equality. Retain those accepted recordings and review their originals before selecting any duplicate capture.

`speed_capture.py:write_original_speed` writes 900 sequential 20 Hz original speed samples and a SHA-256 descriptor once per attempt. `speed_boundary.py:measure` reads that source, rejects missing/stale/noncanonical frame streams, converts SI speed to mph, preserves sample uncertainty, and leaves legal/physical acceptance unresolved. `speed_boundary.py:compare` checks three distinct Native run IDs, fixed authored setup, the declared speed-only target difference, and observed sampled speed ordering. It rejects metadata-only comparison attempts. `tests/test_speed_boundary.py` covers the positive fixture path and missing source, altered hash, malformed descriptor, changed fixed setup, missing case, duplicate run, nonsequential frames and write-once behavior. Synthetic fixtures exercise software only.

Proofs: `.venv-cpu/bin/python runtime.py preflight` passed in `.runtime-work/c10301-preflight.log`; `.venv-cpu/bin/python worker_check.py --updates` returned version 0, no pause. The five focused tests pass in `cpu-speed-boundary-tests.log`. `.venv-cpu/bin/python worker_check.py --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --complete` passes in `cpu-static-check.log`. The same command with `--require-delivery-ready` fails in `cpu-strict-check.log` because status is truthfully partial.

Next CPU work: connect the source writer to a lazy CARLA runner with actual cell geometry, actor identity and source-bound conditions; finalize exact-case measurement contracts, diagnostic recipes and positive/negative compatibility proofs; build canonical proposals, saved-only automation, independent delivery and comparison audits; then rerun the exact strict gate. The 80 mph observation, public-way applicability and actual visibility remain unverified until original physical evidence is reviewed. No legal verdict is claimed.

## 2026-11-24 Native motion checkpoint

`native_motion.py:capture_speed` is a lazy CARLA-facing 900-tick acquisition loop for the exact below/equal/above case IDs. It requires a synchronous 20 Hz world, observed ego velocity/position, a reviewed speed uncertainty input, and a caller-supplied route/camera capture; it writes original speed once through `speed_capture.py`. It rejects frame gaps, clock drift and stalled travel, records a source-hashed motion receipt, and applies full brake on success or failure. It does not claim route/site suitability or physical/legal acceptance. Eight focused tests pass in `cpu-native-motion-tests.log` (SHA256 513d31d273683f09ce44c64e4dec3b2d624352ce969ce6dd697e89608c2eb2cd).

Next: integrate this controller with a reviewed C10301 route and four-camera Native capture; seal authored site/vehicle context, add per-case saved finalization and exact compatibility receipts, then independent delivery/media audit and canonical proposals. Existing accepted summaries remain insufficient to prove 80 mph equality or public-way status.

`saved_speed.py:process` now reads only the original motion receipt and sealed speed source. Default delivery processing rejects diagnostic fixtures; the CPU fake-path test explicitly opts into diagnostic mode, verifies source/receipt joins, and rejects a tampered source hash. No CPU fake is represented as physical Native evidence. Current eight-test log SHA256: 5ce82127d006600a26d564a3684318e539dd363c31b5a0cceb632af047337c04.

`proposals/cases.json` now drafts all three exact numeric-boundary cases with unchanged C10301 cell/actor, the frozen accepted recording IDs, speed-only deliberate difference, original speed and operation-context channels, and explicit unresolved physical/legal calls. It is a draft cases proposal only; other canonical semantic stage proposals, exact site sources, bundles and proof receipts remain.
