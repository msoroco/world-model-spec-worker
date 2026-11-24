# testing__C135087__NRS-484B-517__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.517 — A person shall not stop, stand or park a vehicle other than a bus in a bus stop, or a taxicab in a taxicab stand, when such stop or stand has been officially designated and appropriately signed, except that the driver of a passenger vehicle may temporarily stop there and for the purpose of and while actually engaged in expeditiously loading or unloading of passengers when such stopping does not interfere with any bus or taxicab waiting to enter or about to enter such zone.
Assigned branch(es): Passenger loading with a taxicab entrant.
Cell: C135087 (narrow_road, load_unload, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C135087__NRS-484B-517__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

The original NRS 484B.517 text separates an officially designated, appropriately signed bus stop from a taxicab stand; this assignment's witness is the taxicab-stand passenger-loading branch. No accepted recording exists in the frozen evidence inventory. `case-plan.json` now lists eight exact taxicab-stand cases and seven controlled comparisons covering loading active/ceased, entrant waiting/about-to-enter/absent, and stand access open/constrained. The fixed subject and taxicab classifications, stand geometry, camera contract and driver identity must be reviewed in original sources. No numeric duration, expedience, interference, or sign-adequacy cutoff has been assigned.

`stand.py` provides a source-hash-checked stand and classification adapter, Native map/sign/curb/actor readback, passenger loading and entrant path/access configuration, contiguous original-frame measurements, and comparison isolation. `tests/test_stand.py` exercises construction calls, source tamper rejection, unsuitable taxicab capacity, missing sign readback, frame gaps, missing actors and fixed-condition drift. Eight tests passed. The code does not substitute authored settings for measured outcomes.

Proof commands: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C135087__NRS-484B-517__motor_vehicle_driver/tests -v` exited 0 (`cpu-tests.log`); `.venv-cpu/bin/python worker_check.py --assignment testing__C135087__NRS-484B-517__motor_vehicle_driver --complete` exited 0 (`checkpoint-check.log`); the same command with `--require-delivery-ready` exited 1 (`strict-check.log`, partial/missing package acceptance). This is a partial CPU construction checkpoint. No original Native recording or physical claim is made.

Next CPU work: supply source-sealed stand/designation/sign and vehicle-role records for a real available map; add exact 20 Hz 900-frame runner/config/construction bundles and per-case finalizers, semantic proposals, delivery manifests and saved-only processing; run case-specific offline and positive/negative compatibility plus independent delivery and comparison audits. Test original-site readbacks and every case before readiness. Later CARLA work checks physical placement, taxicab access and full four-camera visibility.

The saved-only `audit_saved_attempt` now rejects non-original source format, incorrect 900-frame/20 Hz profile, absent cameras, stale camera/actor/map hashes, path escape, frame-map discontinuity and missing actor rows. It returns observation counts and source hashes while explicitly leaving full media decode and pixel visibility pending. The 13 focused tests pass, including positive sealed 900-frame input and negative tamper, camera, row and path cases. This verifier does not claim a real capture or full delivery acceptance. `checkpoint-check.log` remains exit 0; `strict-check.log` remains exit 1 at partial/missing package acceptance. The remaining exact-case bundle and compatibility proofs are CPU work.

## 2026-11-23 original source producer checkpoint

`stand_capture.py` now captures the missing producer side of the saved audit. It requires three distinct live actor identities, reviewed map name, a synchronous 20 Hz CARLA world, and four already captured camera files. For 900 ticks it retains the original snapshot frame and time, reads subject and entrant velocities from their actors, and requires four explicit live observer booleans for passenger loading, entrant waiting, entrant about to enter, and access obstruction. Authored case modes are never inserted into observed rows. It seals source hashes for the actor rows, frame map and camera bytes, then invokes `audit_saved_attempt` before writing the attempt source inventory. Camera frame counts and pixels still require pinned media decode and real capture; fixture bytes do not prove either. The existing `stand.measure_original_history` now rejects a 20 Hz time gap even when frame numbers are contiguous.

`stand_capture.py` SHA-256 `f73fdbe4c9b39596983580384cf939ea94d8f1ec4610e9de7f7ca0a488a4d412`; updated `stand.py` SHA-256 `c22950889bb68d5077522ead497ac8b279aa4f199b1c767c3637646921fcf98a`. `PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work/c135087-tmp SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c135087-pipeline .venv-cpu/bin/python -m unittest discover -s work/testing__C135087__NRS-484B-517__motor_vehicle_driver/tests -v` passed 18 tests (`cpu-tests.log` SHA-256 `cdbe2b0d9c09e96d1997a334b38601d7305b610bac2f122c70809ad08dc27341`). Pinned `runtime.py preflight` passed (`preflight.log` SHA-256 `9ebc7a73486b13f0b2cc8ed7e00159f43e9d8b05f17bf85b01264baeb26c04c5`). Scoped `worker_check.py --complete` passed (`checkpoint-check.log` SHA-256 `04130d876ef912bf084e190afa4bc8fc35c120db7f97a6298f40c11011185523`). Exact scoped strict exited 1 at the truthful partial-package gate (`strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Remaining CPU work: bind original source-sealed site/classification records to a real available map, implement the exact CARLA runner/config and camera acquisition for all eight case modes, author the Native result finalizer and semantic proposals, then run per-case offline, positive/negative compatibility, saved processing, full media decode and independent delivery/comparison audits. Keep temporary/expeditious/interference and sign adequacy as sourced judgments, without numeric legal cutoffs. Status remains partial.
