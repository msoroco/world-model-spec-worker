# C213645 / LVMC 11.20.060 delivery handoff

Status: ready, scoped strict CPU gate passed on 2026-11-27.
Assignment: `testing__C213645__LVMC-11-20-060__motor_vehicle_driver`.
Selected branch: residential private driveway entry across sidewalk onto roadway.
The frozen accepted evidence inventory contains zero law-specific recordings and zero judgment ranges for this actor. The selected branch requires a pre-sidewalk stop, pedestrian yielding when necessary to avoid collision, and yielding to approaching roadway vehicles. Judgment probes remain unresolved where the frozen source provides no accepted numeric range; no legal cutoff is invented.

## Exact delivery cases

`sidewalk_stop`, `sidewalk_roll`, `pedestrian_yield`, `pedestrian_intrude`, `roadway_left_yield`, `roadway_left_intrude`, `roadway_right_yield`, and `roadway_right_intrude` are materialized in `cases/` and `execution-manifest.json`. Four pairs isolate the stop, pedestrian, left roadway, and right roadway factors. The paired diagnostic measurements are in `cpu-comparison-*.json`; each audit preserves fixed geometry and reports the actual measured difference without a legal verdict.

## CPU proof result

All 8 cases passed primary and spawn-offset fallback offline proofs, positive and missing-source negative compatibility checks, three saved-source physical outcomes (`met`, `not_met`, `unverified`), the Native ownership lifecycle proof, four-camera source audit positive and missing-camera negative checks, and canonical saved-only processing with original source hashes preserved and final video decoded. `cpu-*.log` and `cpu-*.json` contain the exact receipts. The assignment's 5 unit tests passed in `cpu-unit.log`.

The final command passed with exit 0:

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C213645__LVMC-11-20-060__motor_vehicle_driver --complete --require-delivery-ready`

## Local execution boundary

Run `result.json.first_gpu_delivery_command` for the first exact CARLA job. The CPU fixtures are explicitly synthetic and establish executable preparation only. Actual CARLA vehicle motion, participant visibility, original four-camera pixels, physical completion, and video acceptance remain local delivery checks. Source inventory and provenance fields distinguish them from CPU diagnostic receipts.

## Queue handoff

`gpu-queue-proposal.json` contains all eight exact case jobs with primary, fallback, capture, owner release, saved processing, source audit and acceptance commands, plus the four original-source comparison audit commands. The lead integrates these into the shared ordered queue.
