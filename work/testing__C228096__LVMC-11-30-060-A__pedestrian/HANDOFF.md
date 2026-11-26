# C228096 outside-crosswalk pedestrian delivery handoff

Status: `ready` for CPU delivery preparation. This package has no accepted original roadway capture or legal conclusion. The assigned rule is LVMC 11.30.060(A), with the separate 11.30.060(C)/11.30.070 designated-place exception retained as an original-source review question.

## Selected construction

`execution-manifest.json` binds four exact cases: yield with vehicle, no yield with vehicle, yield without vehicle, and designated prohibited place. Each has a primary and a predeclared slower-path fallback on the same reviewed source site. `case-plan.json` defines the three controlled comparisons and four observation channels. `reviewed_site.py` and `runner.py` require an externally reviewed original OpenDRIVE packet, roadway and marked/unmarked crosswalk geometry, pedestrian and vehicle routes, designated-place status, and four camera poses before Native world mutation. Set `C228096_CROSSING_REVIEW_PACKET`, `C228096_CROSSING_SOURCE_ROOT`, and `C228096_CROSSING_ADAPTER_MODULE` for first capture.

`native_entry.py` records 900 same-tick frames at 20 Hz, pedestrian and all roadway vehicles, four FFV1 cameras, original source identity and Native closure. `analysis.py` finalizes saved channels from the original crossing packet and synchronized frame map. The physical completion config uses the pinned runtime's supported `travel_progress` criterion with a 5 m engineering proxy; independent original-source review must establish the actual roadway crossing and yield trajectory. This engineering distance is not a legal threshold.

## CPU proof

- 8/8 selected primary/fallback offline checks and 8/8 source-hashed positive/negative diagnostic compatibility checks pass; receipts are in `cpu-offline-proofs.json` and `cpu-compatibility-proofs.json`.
- 4/4 saved-only processing checks, 4/4 independent delivery audit positive/missing-source pairs, and 3/3 comparison audits pass; receipts are `cpu-saved-proofs.json`, `cpu-independent-proofs.json`, and `cpu-comparison-proofs.json`.
- Four case physical preparation receipts cover complete/incomplete/missing synthetic motion and Native owner-release lifecycle. `cpu-runtime-physical-proof.json` additionally exercises the selected criterion through pinned `assess_physical` and records `met`, `not_met`, and `unverified` outcomes.
- `cpu-current-validators.log` records selected manifest, semantic, delivery and compatibility validator success. `cpu-final-tests.log` records 8 source/geometry unit tests. Synthetic diagnostic evidence proves software behavior only.

The exact scoped command `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__LVMC-11-30-060-A__pedestrian --complete --require-delivery-ready` passes. `gpu-queue-proposal.json` lists first GPU prepare/execute, saved processing, independent source audit, acceptance, fallback and comparison commands. Root coordinates queue integration after independent rerun.

## First GPU review

Obtain a reviewed original roadway packet that establishes the crossing point outside both crosswalk categories, includes 11.30.070 designated-place context, and positions the pedestrian, all roadway vehicles and four cameras. Execute each selected case, retain original source hashes, inspect synchronized pedestrian and vehicle motion and all four decoded videos, then run independent saved delivery and comparison audits. Physical realization, actual right-of-way behavior, and statutory application remain unverified until that review.
