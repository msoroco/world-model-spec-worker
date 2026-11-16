# C147311 CPU handoff — NRS 484B.220(1)

Status: **partial**. Fixed cell: one-way multilane, travel, direction sign. The law requires the highway to be designated and signposted for one-way traffic, then the vehicle to move only in the designated direction. Frozen accepted-evidence inventory is empty.

`native_one_way.py` inventories at least two same-signed Native driving lanes on one road; this does not prove authority designation or signs. `one_way_measurements.py` joins original frames to complete ego bodies, sourced roadway polygon and designated direction, then reports motion projections and heading. Three CPU tests pass for positive/negative direction, wrong lane, stale frame and opposing-lane selection. The synthetic tests are implementation checks, not physical/legal acceptance.

Next CPU work: source the public designation and signposting; construct the exact Native route and direction sign with both positive/negative motion. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual motion and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C147311__NRS-484B-220-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C157964__NRS-484B-257-2__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## Paired route and independent comparison checkpoint

`native_one_way.paired_route_points` now builds with-designation and against-designation route point lists by reversing the same sampled Native driving lane. It rejects a lane outside the selected multilane set, invalid designated vectors, insufficient waypoints and a span shorter than 12 m. The route is an engineering construction plan only; the authority designation, installed signs and actual Native wrong-way motion remain unverified.

`comparison_audit.py` independently recomputes both original-frame measurements. It requires identical hashed road context, selected lane sequence, frame count and roadway occupancy, then checks positive versus negative measured heading and projected displacement. Its CPU fixture rejects changed sign context and a nominal negative case that actually travels in the designated direction. The audit leaves physical and legal acceptance unresolved. Five tests pass in `cpu-tests.log`; `result.json` binds its current SHA-256. The assignment `--complete` check passes in `assignment-check.log`; the assignment strict ready gate exits 1 in `strict-gate.log` because the package remains partial.

Next implement a reviewed designation/sign packet and sign construction, then the exact case runner, four source cameras, saved finalizer and runtime offline/compatibility/process-saved proofs. Expand the two cases with physical-risk fallbacks and semantic proposals, and add the independent source-decoded delivery audit. These remain CPU preparation tasks; no external blocker is asserted.

## Paired controller checkpoint

`direction_control.py` now supplies one route follower for each point order returned by `paired_route_points`. It observes position, forward vector and speed, applies bounded steering and speed control, advances waypoint targets, and brakes at the final point. The sixth CPU test exercises both travel orders, route completion, steering sign and invalid route rejection. It does not simulate CARLA dynamics or certify that a vehicle can physically drive against a Native lane.

After this change, the six-test suite passes (`cpu-tests.log`, hash in `result.json`) and assignment `--complete` passes (`assignment-check.log`). The exact assignment strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`) because `result.json` truthfully remains partial. The integrated runner, real designation/sign review, exact-case offline and compatibility receipts, saved processing, fallbacks, semantic proposals, and source-decoded audits are unfinished CPU work. No external prerequisite is asserted as a blocker.

## Site packet source check

`site_review.py` now checks that a proposed one-way designation has a byte-hashed source document and exact text, and that each one-way sign has a distinct identity, hashed source, position, selected road and both selected lanes. `native_one_way.prepare_reviewed_route` joins that packet to the Native map and paired route plan before capture. The synthetic CPU fixture exercises the joined construction and rejects a stale sign hash and incomplete lane coverage. The check intentionally leaves the authority of the designation and actual sign visibility for independent site review. No real packet is present yet.

The seven-test suite passes and its current log hash is in `result.json`; the assignment `--complete` static check passes. The assignment strict command still exits 1 with the exact message `Preparation acceptance failed: partial/missing packages remain` because the executable case bundle and its proofs are unfinished. Next provide a real reviewed site packet and integrate `prepare_reviewed_route` and `RouteFollower` into the exact runner, then build source cameras, saved finalizer, required proposals/fallbacks/audits and exact runtime receipts. No GPU or source gap is being substituted for these CPU tasks.

## Saved measurement source join

`one_way_measurements.analyze` now requires `site_packet.json` plus the byte-hashed designation and sign documents in the saved attempt. It joins the packet to the road context and refuses missing or stale files. The independent comparison audit requires identical site packet and source bytes across the with/against pair, in addition to its existing road, lane and observed direction checks. The eighth CPU test rejects an absent packet and changed sign source; the comparison test rejects a source change between cases. All eight tests pass (`cpu-tests.log`, hash in `result.json`).

The current exact assignment `--complete` static check passes; `--complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. The package is still a partial construction checkpoint. The next CPU step is a real site packet and integrated exact runner with source cameras, followed by the full saved-processing, fallback, proposal and delivery-audit work. The synthetic packet used by tests does not establish real signposting.
