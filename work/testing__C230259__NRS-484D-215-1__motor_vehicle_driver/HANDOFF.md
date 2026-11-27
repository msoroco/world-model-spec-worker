# C230259 — NRS 484D.215(1) moving road beams

Status: **ready for local physical delivery**. The exact scoped gate passed on 2026-11-27:

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C230259__NRS-484D-215-1__motor_vehicle_driver --complete --require-delivery-ready`

The package has eight selected source-bound cases and six controlled comparisons. Cases cover ordinary high/low/dark distribution; oncoming 499-foot high/low, 500-foot low, and 501-foot low; and a 499-foot low-beam crest/loaded variant. These are requested engineering positions; original frame measurements determine the actual exposure. No numeric safe-visibility or glare threshold was invented. The frozen accepted inventory has zero original recordings, so physical facts and legal judgments remain for independent review.

## CPU proof and prepared delivery

- `execution-manifest.json` has eight selected entries, a primary and alternate camera pose candidate per entry, measurement contracts, source-hashed diagnostic recipes, saved-only processing and post-capture delivery commands.
- All eight primary and eight fallback1 candidates passed runtime offline and compatibility proofs after the final source/plan refresh (32 successful proof commands). All eight primary diagnostic captures passed the recorded-only lifecycle and `process-saved` CPU proof.
- Eight delivery audits and six comparison audits passed positive and negative diagnostic tests. These synthetic diagnostic fixtures prove pipeline wiring and rejection behavior; they are not original optical evidence.
- Thirty-five local CPU tests passed. The package manifest, semantic proposals, all delivery entries and compatibility receipts passed standalone validators. The exact strict assignment gate passed with `result.json` marked `delivery_prepared`.
- `queue-proposal.json` gives the lead eight exact case entries and six comparison audit entries for integration into `work/_shared/gpu-queue.json`. `queue-command-catalog-proposal.json` contains the exact commands behind each dispatch wrapper. The owner release and saved processing commands take `ATTEMPT_DIR`, while acceptance takes the numeric `ATTEMPT`. The first canonical GPU dispatch command is in `result.json`.

## Physical review remaining

The Native runner captures 900 synchronized 20 Hz frames, original actor and lamp state, body and eye distances, source joins, reviewed projection regions, four lossless video views, road/graph receipts and an acquisition provenance marker. It restores CARLA settings and owned actors after the run. Physical CARLA motion, camera framing, emitted illumination, visibility at a safe distance and oncoming eye glare require original local capture and independent review. The lowermost distribution's statutory deeming rule is preserved without equating a requested mode or CARLA bit with a proven statutory distribution.
