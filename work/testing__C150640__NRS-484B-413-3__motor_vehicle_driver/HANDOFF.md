# C150640 rear-recipient signal delivery handoff

Status: CPU delivery prepared for five exact selected cases and four controlled comparisons. The selected frozen cell is C150640, one-way road, stop/stand, other vehicle; actor is motor vehicle driver. NRS 484B.413(3) says a driver shall not stop or suddenly decrease vehicle speed without first giving an appropriate signal to the driver of any vehicle immediately to the rear. Zero accepted original recordings are in the frozen inventory. No legal verdict or original physical acceptance is claimed.

## Exact construction

The five cases are `stop_signal_before`, `stop_signal_after`, `decrease_signal_before`, `decrease_signal_after`, and `stop_no_rear_driver`. `runner.py` requires a reviewed original `C150640_REVIEWED_SCENE_PACKET`. `scene_review.py` checks source-file hashes and the selected identity. `native_signal.py` constructs separate ego and rear vehicles, a rear driver actor when required, a source-bound one-way route and stop footprint, an actual CARLA signal light, before/after control timing, 900 original frames, two-actor motion, a rear mounted driver view, three external views, Native seal and world restoration. Actual rear driver placement, displayed signal visibility and separation must be reviewed in the original run.

`rear_signal.py` measures the original 900-frame participant IDs, rear gap/offset, ego/rear speed, signal display and visibility readback, and event versus signal onset. It leaves signal appropriateness, immediately-to-rear status, conflict/official-direction context, and legal outcome unresolved. Engineering speed checks verify the authored physical probe; they are not statutory thresholds.

The comparisons are `stop_signal_order`, `decrease_signal_order`, `stop_vs_decrease`, and `rear_driver_presence`. `comparison_audit.py` accepts only original delivery audit reports, checks the fixed source hashes, camera plan and duration, and requires the intended measured difference. The assignment-local `queue-proposal.json` has five selected case rows and four original-only comparison rows. There are no fallback candidates because the reviewed route, rear participant and signal device are absent; no distinct source-grounded alternate construction is available yet.

## CPU proof

- Ten focused tests pass, including all five exact original-frame probes, source packet tamper/identity checks, inline construction binding, and four comparison contrasts.
- Five exact offline constructions and pinned compatibility positive/negative receipts pass at current construction hashes.
- Five physical/lifecycle probes pass complete, incomplete and missing-evidence states, including Native exit, owner release and saved-source staging.
- Five recorded-only saved replays and mock delivery audit positive/negative probes pass. These are synthetic software checks and make no original physical claim.
- Direct execution-manifest, semantic-delivery, delivery-handoff, and shadow ready checks pass 5/5. The scoped complete static check and focused tests are recorded in `cpu-nov25-static-current.log` and `cpu-nov25-tests-current.log`.

## Original delivery boundary

Acquire a reviewed original scene packet with the required jurisdiction, one-way route, rear driver and participant positions, signal device/visibility, stop footprint and conflict/official-direction sources. Use the canonical commands in `queue-proposal.json`. Retain original CARLA recorder, four videos, 900 joined rear-signal rows, map, reviewed scene packet, Native seal/exit/owner release, saved processing and full-decode receipts. An independent reviewer must inspect actual signal and rear-driver pixels and record `pixel-review.json`; `queue_delivery.py` verifies original sources, physical completion and pixel review before writing its audit. The four comparison audits require accepted original reports. Actual rear-driver visibility, signal suitability, “immediately to the rear,” and legal interpretation remain open for local review.
