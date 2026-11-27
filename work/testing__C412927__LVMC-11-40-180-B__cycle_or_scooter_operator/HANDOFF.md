# LVMC 11.40.180(B) / C412927 signed roadway

Status: `ready` for CPU-prepared delivery. The exact scoped strict gate passed on 2026-11-26:

`SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c412927-owner/output PYTHONDONTWRITEBYTECODE=1 TMPDIR=.runtime-work/c412927-owner/tmp .venv-cpu/bin/python worker_check.py --assignment testing__C412927__LVMC-11-40-180-B__cycle_or_scooter_operator --complete --require-delivery-ready`

Result: `static_checks_passed: true`; see `.runtime-work/c412927-owner/strict-attempt-5.log` for the local log. The assignment has seven exact cases and five controlled comparisons. The ordered local GPU proposal is `queue-proposal.json`; the case and comparison definitions are in `case-plan.json` and the final `execution-manifest.json`.

The seven cases cover bicycle, electric bicycle, and electric scooter riding through an in-place governed sign; bicycle turning away before the restriction; and bicycle controls for an absent sign, movement outside its extent, and walking the device. The five comparisons cover sign obedience, covered device alternatives, posting, extent, and riding versus walking. No statutory speed or distance cutoff is inferred.

The original law requires an actual City of Las Vegas roadway, a Director of Public Works order, consultations with the City Traffic Engineer and Las Vegas Metropolitan Police Department, a Director determination about pedestrian or vehicle traffic flow, and an in-place sign governing the precise route and device. The frozen cell supplies only paved road, travel, and an access restriction sign. The original source packet must establish the remaining facts and its source hashes before Native execution. The source gate rejects unreviewed or changed records and changed sign scope. A legal finding is never derived from simulation alone.

CPU evidence: four unit tests pass; all seven cases passed offline construction and positive/negative compatibility; all seven passed physical outcome, incomplete motion, missing evidence, and saved-only lifecycle checks; all seven passed positive and negative independent delivery audit probes; all five comparison audit positive and negative probes pass. The manifest records the per-case proof logs and hashes. Diagnostic bundles and temporary files are under `.runtime-work/c412927-owner/`.

The next stage is source review, CARLA motion and four-camera capture, saved processing, independent source/media audit, comparison audit, and operator acceptance using the commands in `queue-proposal.json`. Actual GPU capture has not been claimed by this CPU-ready result.
