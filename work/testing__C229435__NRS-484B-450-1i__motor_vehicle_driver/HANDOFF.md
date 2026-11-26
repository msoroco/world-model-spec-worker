# C229435 nearest-rail parking delivery handoff

Status: `ready` for CPU delivery preparation. No accepted original railroad recording or legal conclusion is claimed. NRS 484B.450(1)(i) prohibits stopping, standing or parking within 50 feet (15.24 m) of the nearest railroad rail, subject to independent traffic-conflict necessity and law, officer or official-device exceptions. This assigned cell is the parking branch with another vehicle; that vehicle's presence alone does not establish necessity. Exact boundary interpretation remains for original/legal review.

## Selected construction

`execution-manifest.json` binds four exact cases: inside 14 m with no exception, at 15.24 m with no exception, outside 17 m with no exception, and inside 14 m with traffic necessity unresolved. `case-plan.json` defines three controlled comparisons. Each case has a primary and a slower approach fallback on the same reviewed source site. `reviewed_site.py` requires an externally reviewed, source-hashed original OpenDRIVE, railroad identity and carrier provenance, every nearby rail polyline, complete planned ego footprint and route, distinct other-vehicle route, four separate exception reviews and four camera poses before Native world mutation. Set `C229435_RAIL_REVIEW_PACKET`, `C229435_RAIL_SOURCE_ROOT` and `C229435_RAIL_ADAPTER_MODULE` for first capture.

`native_entry.py` captures 900 same-tick 20 Hz ego/other vehicle rows and four FFV1 camera streams, records original source identity and seals Native ownership. `rail_proximity.py` measures the complete vehicle footprint to every nearby rail segment and chooses the nearest; separated collinear rail/footprint segments are tested. `analysis.py` finalizes four saved observation channels from original rail, vehicle, exception and synchronized frame sources. The selected physical completion criterion is pinned-supported `travel_progress` on original ego trace with a 3 m engineering approach proxy. Independent delivery audit separately checks the parked final action, raw nearest-rail distance, both vehicle trajectories, frame joins and full video decode. Approach progress is not parking or legal acceptance.

## CPU evidence

- 8/8 selected primary/fallback offline checks and 8/8 source-hashed positive/missing-source compatibility checks pass; see `cpu-offline-proofs.json` and `cpu-compatibility-proofs.json`.
- 4/4 saved-only processing proofs, 4/4 independent delivery positive/missing-source pairs and 3/3 exact saved comparison audits pass; see `cpu-saved-proofs.json`, `cpu-independent-proofs.json` and `cpu-comparison-proofs.json`.
- Four case physical preparation receipts cover synthetic complete/incomplete/missing motion and Native owner-release lifecycle. `cpu-runtime-physical-proof.json` also exercises pinned `assess_physical` with synthetic `met`, `not_met` and `unverified` outcomes.
- `cpu-current-validators.log` records selected manifest, semantic, delivery and compatibility validator success. `cpu-final-tests.log` records nine source, rail geometry and segment tests. All diagnostic evidence is synthetic software proof only.

The exact scoped command `.venv-cpu/bin/python worker_check.py --assignment testing__C229435__NRS-484B-450-1i__motor_vehicle_driver --complete --require-delivery-ready` passes. `gpu-queue-proposal.json` lists four case jobs, fallback, saved processing, independent audit and three comparison commands. Root coordinates queue integration after independent rerun.

## First GPU review

Obtain an original site packet with carrier provenance and complete nearby rail inventory. Execute each case, verify the actual parked vehicle footprint and nearest physical rail, inspect both vehicle trajectories and four decoded videos, then run independent delivery and comparison audits. Review traffic necessity and law/officer/device directions separately. Treat the 15.24 m boundary as a raw measurement requiring legal interpretation, not a fixture verdict.
