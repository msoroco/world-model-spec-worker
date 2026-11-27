# C412974 / NRS 484B.110 safety-zone travel

Status: CPU delivery prepared. The exact scoped strict gate passed. This is a software preparation claim. No CARLA capture, original pixel review, canonical local acceptance or legal verdict occurred here.

## Frozen scope and evidence

The exact law says: “No vehicle shall at any time be driven through or within a safety zone.” The assigned cell is paved road, travel, safety zone, with a motor-vehicle driver. The frozen evidence inventory lists zero accepted recordings. The conditional witness requires an official pedestrian-only designation, boundaries and interval, marking/sign visibility, qualifying vehicle and driver, a public highway, and original vehicle extent and motion. `case-plan.json` maps the one evidence gap to every selected case and records the fixed comparison conditions. No training judgment range applies to this law and actor.

The source-bound Native entrypoint requires `C412974_REVIEWED_SITE_PACKET` to name an independently reviewed original packet. `site_review.py` checks its map OpenDRIVE hash, each source file hash, exact case identity, official designation/marking provenance, physical boundary marker specifications, highway, driver and vehicle context. A visible marker alone cannot establish official status. The unverified-designation case records an unresolved source status; it does not assert that no designation exists.

## Exact cases and comparisons

Four planned full-test recordings, with zero Native executions and zero accepted recordings:

- `testing__C412974__NRS-484B-110__motor_vehicle_driver__through_zone`: original route and body transit into then out of an active, source-verified zone.
- `testing__C412974__NRS-484B-110__motor_vehicle_driver__within_zone`: original body ends within the active zone.
- `testing__C412974__NRS-484B-110__motor_vehicle_driver__beside_zone`: route beside the same active zone without body overlap.
- `testing__C412974__NRS-484B-110__motor_vehicle_driver__through_unverified_designation`: same through route with official designation unresolved by the source packet.

`through_vs_beside` changes only the selected route relative to fixed zone boundaries. `through_vs_within` changes the terminal route. `through_vs_unverified` changes designation source status while retaining the through route. Each comparison is source-gated by `comparison_audit.py`; no comparison has been physically completed. The source-limited contrast is not a legal compliance label.

## Construction and CPU proofs

`zone_motion.py` validates the public-highway, vehicle, driver, official-zone and route source context, computes original body intersection area, and checks 900 joined original frames at 20 Hz. `runner.py` gates the reviewed source packet; `native_zone.py` builds physical boundary markers, spawns and controls the motor vehicle, records synchronized four-camera views and original body/motion histories, then restores the world. `analysis.py` processes saved Native data, validates acquisition hashes and frame joins, emits every mandatory channel and preserves a null legal judgment. The four exact constructions are in root and `cases/`; the primary and gentler common `fallback1` both have offline and positive/negative compatibility receipts in `cases/`. The fallback is triggered only by original route or visibility failure, without changing a law variable.

`run_cpu_proofs.py` passed eight offline checks and eight positive/negative compatibility checks against the current runtime. `run_saved_proofs.py` passed four saved-only processing replays. `run_physical_proofs.py` passed complete, incomplete, missing-evidence and ordered-lifecycle fixtures for all four cases. `run_delivery_proofs.py` passed four delivery protocol positives and four missing-source rejections. `run_comparison_proofs.py` passed three positive/negative independent comparison-shape checks. `cpu-tests.log` contains the focused geometry/source tests. Synthetic fixtures demonstrate software behavior only and have no physical-acceptance claim. The exact acceptance command passed:

`.venv-cpu/bin/python worker_check.py --assignment testing__C412974__NRS-484B-110__motor_vehicle_driver --complete --require-delivery-ready`

`proposals/semantic-index.json` binds all canonical stage proposals. `execution-manifest.json` binds exact source hashes, construction and proof receipts, post-capture code, physical preparation and delivery-audit commands. `gpu-queue-proposal.json` contains the four exact local dispatch rows and three comparison commands for lead integration. Only the lead edits shared queue files.

## Local execution and remaining original checks

The local operator supplies the reviewed site packet, CARLA Python and four-camera capable map, then uses the queue's prepare, execute, owner-release, postprocess, source-audit and accept commands. `delivery_audit.py` independently requires original sealed Native sources, owner release, source-bound saved processing, full frame join, complete physical motion, current full-video decode receipt and actual-pixel review. The original official designation and continuing sign/marking visibility, route and body motion, camera coverage and pixel visibility remain unverified until that local run. Exact comparison acceptance requires two independently accepted original reports with fixed source conditions and measured deliberate differences.
