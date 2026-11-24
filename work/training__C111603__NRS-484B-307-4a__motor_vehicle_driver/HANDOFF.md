# training__C111603__NRS-484B-307-4a__motor_vehicle_driver

Status: **partial**. No selected delivery cases, CARLA construction, CPU candidate proof, CARLA execution, or accepted recording is claimed.

Exact source: `inputs/training__C111603__NRS-484B-307-4a__motor_vehicle_driver/assignment.json` SHA-256 `5548bd0e3c0bd1a3b8e1d78182730e27d43196ed71c16e7c0fc5360f11d1eb2a`; witnesses: `inputs/training__C111603__NRS-484B-307-4a__motor_vehicle_driver/witnesses.json` SHA-256 `70b5f21bf036655fed1b6a2feb36c3053d51c0bb2609c7a4d5a1b8cd6e811c59`. The statutory text and source citation are retained in `case-plan.json`; recovered summary is unreviewed.

Frozen cell: `intersection` / `turn` / `other_vehicle`; actor `motor_vehicle_driver`. Proposed contrast: **arrow direction and priority**. 3 unselected planning probes are in `case-plan.json`. Baseline is unselected.

Blocker: Lawful participant status cannot be inferred solely from position; retain authored source and measured crossing. 0 unique accepted membership IDs are contextual and have no local source-hashed equivalence proof.

Resume: review exact branch and exception context against law and witness, prove any eligible accepted equivalence, resolve same-cell physical support, then implement four distinct Native candidates for each genuinely selected case. Run runtime offline/compatibility recipes, semantic-stage and saved positive/negative audits, comparison audits, and set `ready` / `delivery_prepared` only after all worker-owned CPU proofs pass. Keep legal standards unresolved pending measured evidence.

## Green-turn-arrow saved-source CPU checkpoint

`native/arrow_measure.py` measures 600 joined 20 Hz signal and participant frames against an explicit intersection and adjacent-crosswalk context. It separately reports first ego entry, motion while the arrow is unlit, heading direction mismatch, motion while a pedestrian occupies the crosswalk, and motion while other traffic occupies the intersection. Source SHA-256 hashes bind all three required input files. `arrow-measurement-contract.json` maps every frozen observation term to a measured source or unresolved physical context. The output explicitly leaves governing-head pixels, participant lawfulness and yielding causation unverified.

`prove-arrow-measurement.py` generated four 30-second source-shaped positives under `.runtime-work/c111603-proof`: ego pause during participant occupancy, moving overlap with pedestrian and other traffic, opposite turn heading, and motion during an unlit interval. It rejected missing signal source and a corrupt Native frame join. Exit 0; `arrow-measurement-proof.log` SHA-256 `eebbb26133cbac7c9477096915933f8b3bbf2a31d5408a7a05c41000c423c738`; measurement script SHA-256 `2c7335b4dc9872e497d6a7151fa8816711a28d59e22dfcc10c55ddf659d22b71`. These generated diagnostics establish software behavior only.

Next CPU work: author a real Native governed green-turn-arrow construction and original four-camera capture, bind original signal pixels and ego/participant motion, select exact delivery cases after source review, then run pinned offline, saved positive/negative, independent acceptance and controlled comparison audits. Independent physical review must establish that the arrow head faces and governs the ego, that the pedestrian and other traffic are lawfully present, and whether the ego actually yielded. No case is ready.
