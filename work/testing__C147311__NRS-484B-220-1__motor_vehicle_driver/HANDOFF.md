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

## Integrated with-designation primary CPU path

`runner.py` now contains a lazy CARLA capture that inventories two same-signed Native driving lanes, joins the byte-hashed site packet, selects the same-lane with-designation waypoint route, spawns the requested Native vehicle and follows it using `RouteFollower`. It records complete-body travel/heading/lane source rows, original frame/video joins, four FFV1 source cameras and Native graph capture, then restores world settings and seals the attempt. The `--check` path does not contact a simulator. The inline `site_packet.json`, designation text and sign text are explicitly synthetic; they do not establish public authority, installed sign status or visibility.

`finalizer.py` derives per-frame designated motion, heading alignment and roadway occupancy from saved `one_way_measurements.analyze` sources, and writes a pinned Native-shaped result plus measurement report. It rejects absent original travel history and stale designation/sign source bytes. The nine-frame diagnostic fixture supplies a synthetic two-lane OpenDRIVE road, original-shaped graph/frame/trace joins and four lossless videos; it is a software test rather than a physical recording.

Exact primary `runtime.py offline` passes at `.runtime-work/c147311-with-offline-v2` (`exact-offline.log`). Exact positive/negative `runtime.py compatibility` passes at `.runtime-work/c147311-with-compat-v2`, including pinned conversion, Lean decoder and render; it rejects a missing `travel_history.jsonl`. Recorded-only `runtime.py process-saved` passes at `.runtime-work/c147311-with-saved-v1`. Current copied receipts/logs are bound in `execution-manifest.json`, and pinned `package_compatibility.check_receipts` passes. Eight assignment tests pass with current hash in `result.json`.

The against-designation selected case still needs its construction and exact CPU path. Three risk-triggered fallbacks per selected case, reviewed real authority/designation/sign sources, semantic chain, physical-preparation and independent full-duration delivery/comparison audits remain worker-owned CPU work. Keep status partial; actual Native direction and sign visibility are later physical checks.

## Against-designation selected case and source comparison

`cases/against-construction.json` selects the same Native map, road, lane, designation/sign packet, source cameras and 45-second capture as the with-designation case, then reverses the authored waypoint order and heading. `cases/against-diagnostic.json` mirrors that deliberate difference in original-shaped body, velocity, heading and graph rows. These rows are synthetic software inputs; they do not demonstrate that a Native vehicle can travel wrong-way.

The against case passes exact `runtime.py offline` at `.runtime-work/c147311-against-offline-v1`, positive/negative `runtime.py compatibility` at `.runtime-work/c147311-against-compat-v1`, and recorded-only `runtime.py process-saved` at `.runtime-work/c147311-against-saved-v1`. Logs and copied receipts are under `cases/` and bound in `execution-manifest.json`. Pinned `package_compatibility.check_receipts` passes for both selected cases with current construction, recipe, source measurement and missing-travel-history negative hashes.

`comparison_audit.audit` passes against the two retained compatibility attempts and writes `cases/comparison-receipt.json`: nine paired frames on the same sourced road/lane, identical hashed designation and sign documents, complete body on the roadway, and opposite observed heading/displacement. The audit rejects changed sign source and nominal wrong-way motion that actually follows the designation in unit tests. Authority, physical and legal conclusions remain unresolved.

Remaining CPU readiness work is reviewed real designation/authority and installed-sign sources, three distinct physical-risk fallbacks per selected case, semantic chain, physical-preparation proof and full-duration independent delivery audit. Preserve partial status until strict gates pass.

## Risk-triggered fallback CPU paths

Each selected direction case now has three separate construction fallbacks in `cases/`, bound to the same road, lane, designation/sign packet, 45-second capture and four original source cameras. Fallback 1 lowers the original vehicle's requested speed if complete-body roadway or selected-lane occupancy fails. Fallback 2 requests an alternate Native vehicle blueprint if subject spawn fails. Fallback 3 adjusts the authored source camera positions if the vehicle or sign is clipped. These are distinct physical failure triggers; none claims a successful Native run. In particular, the fixed synthetic diagnostic fixture does not prove that the alternate blueprint will spawn.

All six fallback constructions pass exact `runtime.py offline`, pinned positive/negative `runtime.py compatibility`, and recorded-only `runtime.py process-saved`. Each compatibility negative removes `travel_history.jsonl`; each saved receipt reports `passed`, `recorded_only` and `originals_preserved`. The copied receipts and exact logs are under `cases/` and bound by hash and command in `execution-manifest.json`. Pinned `candidate_constructions.validate` passes for each selected case with four candidates (primary plus three fallbacks), and `package_compatibility.check_receipts` passes for both primaries.

Status remains **partial**. The site designation and sign packet is synthetic; a real reviewed authority designation, installed-sign evidence, semantic chain, physical-preparation proof and independent full-duration source-decoded delivery audit remain worker-owned CPU requirements. Actual Native wrong-way motion, sign visibility and legal acceptance are unproved.

## Independent source decode audit scaffold

`delivery_audit.py` independently checks the exact 20 Hz/45-second config, ordered frame/time joins, saved one-way measurements and contract source hashes, and decodes all four original camera files with the pinned media auditor. It passed both retained nine-frame diagnostic compatibility attempts and wrote `cases/with-diagnostic-delivery-audit.json` and `cases/against-diagnostic-delivery-audit.json`. Its default 900-frame delivery check correctly rejects the nine-frame fixture with `Full original frame-map duration required`. This proves the audit path is executable and enforces duration; it cannot produce a full-duration receipt before an actual 900-frame Native attempt exists. Pixel review of sign visibility also remains to be implemented.

## Canonical semantic and physical preparation checks

`proposals/semantic-index.json` now binds the five canonical relevance, template, binding and cases stages by SHA-256. The template represents the exact supplied one-way condition and direction duty without inventing a numeric threshold or deciding whether the synthetic designation and sign are official. A shared baseline and linked with/against attempts use the same recording description as the selected constructions. Pinned `semantic_delivery.validate` passes with two selected cases (`semantic-validation.log`). This is a draft proposal chain for local review, not a legal verdict.

The ninth CPU test now runs the integrated `runner.prepare_site` path for both direction orders on a fake two-lane Native map, then exercises four named source-camera spawn and cleanup calls for each route. It checks opposite route starts and confirms that sign visibility remains unverified. All nine tests pass. This is physical preparation on a CPU fixture; it does not prove a real TownX map, installed sign, camera pixels or vehicle dynamics. The exact assignment `--complete` static check passes; strict delivery readiness remains partial for the source and full-duration gaps above.
