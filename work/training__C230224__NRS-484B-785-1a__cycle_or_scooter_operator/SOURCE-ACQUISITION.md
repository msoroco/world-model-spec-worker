# C230224 original source acquisition

The frozen selected scene is an electric scooter traveling on a path. The selected operating-speed requests are 12, 15 and 17 mph; original Native velocity and pose, not the requests, determine realized speed and occupancy. The motor-only scooter classification maximum of 20 mph is a different fact from the statutory 15 mph operating cap.

## Reviewed input before Native dispatch

Bind a genuine rideable electric-scooter asset and rider to source records for handlebars, electric motor, riding design, propulsion, rider-excluded mass at most 100 lb, and motor-only maximum at most 20 mph. Record the actual Native blueprint and rider actor IDs and the source hashes. Reject a bicycle blueprint or an unreviewed classification. Survey the path surface, continuity, access, neighboring roadway boundary, spawn point, travel axis and four camera transforms; preserve measurement or map source hashes. Acquire the applicable NRS 484A.469 ordinance and any contrary posting/local definition, with jurisdiction and effective-time review. An ordinance exception may replace the default rule only when its source and applicability establish that effect; no substitute speed is inferred from permission to use the path.

## Original attempt evidence

For every exact case, capture 600 joined frames at 20 Hz over 30 seconds. Preserve `video_frames.jsonl`, `native_rider_trace.jsonl`, `trace.jsonl`, four original cameras (`overview.mkv`, `approach.mkv`, `reference_corner.mkv`, `driver_reference.mkv`), `scooter_context.json`, Native lifecycle/owner-release receipt and original source hashes. The trace must retain device and rider identity, scooter center pose, Native velocity, camera frame mapping and measured path geometry. Attach `scooter-original-review.json` with source hashes, original pixel review, scooter classification, path occupancy, ordinance applicability and posting review. Complete review is source-specific; synthetic diagnostic markers are rejected in original mode.

## Post capture audit

Run recorded-only processing after Native ownership release. Then run `native/delivery_audit.py --case ID --attempt ATTEMPT` without a diagnostic flag. It validates exact source identities, all participants, time join, 600-frame full video decode and RGB bytes, review hashes and measured physical completion. Run `measure_scooter.py` on each saved attempt and `audit_comparison.py` with each exact `comparison_id` on the saved source-bound measurements. A requested 15 mph target is not a realized 15 mph measurement. Keep ordinance, posting and facility judgments unresolved unless original sources establish them. The independent audit returns no legal verdict.

Current `original-mode-negative.log` proves that a synthetic current-runtime compatibility attempt is rejected at the original Native source review boundary. The selected diagnostic positive/saved receipts are CPU mechanics proofs only.
