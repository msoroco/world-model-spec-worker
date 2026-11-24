# LVMC-11-27-010-A at C143691

Actor: `motor_vehicle_driver`. Frozen cell: `nonmotorized_trail` / `travel` / `barrier`.

Exact statutory source: LVMC 11.27.010(A); with 11.27.010(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Conjunctive trail prerequisites, subject to all Subsection (B) exceptions.

Controlled planning variable: `motorized_trail_occupancy`. Proposed requests: ordinary motor vehicle stays outside posted dedicated designated trail right-of-way; same vehicle enters trail right-of-way. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: three conjunctive trail prerequisites; emergency vehicle; maintenance vehicle; mobility device.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/route.py` now requests paired 600-frame / 20 Hz trajectories with one controlled lateral difference: staying outside versus traveling within the planned trail right-of-way. The route proof `native/route-proof.json` (SHA-256 `5515e4dbd894d43d2ab6629529f030fdea014d558b76b39bd1c3a058a0931559`) checks the same forward speed/position, a traversable barrier-gap request and three negative scene mutations. This is an engineering route proposal, not observed CARLA motion or a determination that the actual barrier is passable.

`native/measure_trail.py` and `native/measurement-contract.json` require original Native footprint, frame/time and four source-camera identities plus independent designation, dedication, posted-sign, vehicle-identity and map sources. The source-shaped CPU proof `native/trail-proof.json` (SHA-256 `7d7b64f1bca080d93aa3b2319244d417a90a44d8f7db0709aad249e06ad25656`) distinguishes zero versus positive trail occupancy and rejects nine source, barrier and frame defects. The fixture uses placeholder hashes and cannot establish the administrative facts, physical entry, sign appropriateness, exception status or legal outcome.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire a CARLA runner to the route and four cameras; build exact cases and risk-based candidates; source and measure emergency, maintenance and mobility-device exceptions; run exact offline, compatibility, saved-only and independent delivery/comparison proofs. Then run the assignment-scoped strict ready gate before any promotion.

## 2026-11-23 subsection B exception CPU checkpoint

The trail meter now requires an exception identity and source hash. It checks a maintenance vehicle is claimed to be used on this right-of-way, and a mobility device is claimed both designed for and used by a mobility-impaired person. Three same-occupancy source-shaped exception branches (emergency vehicle, right-of-way maintenance, mobility device) measure positive trail occupancy without assigning legal compliance. New negatives reject an absent exception source, maintenance without this-right-of-way use, and mobility device without user evidence; all 12 negatives pass. Refreshed `native/trail-proof.json` SHA-256 `d5e572c8eef6069299577b634c6b1e67fd3585b317ebbabb3b719466ca488251`; meter SHA-256 `ff829918dcc734609766ad3c7761e94502dd7f19483c8f95027621fb3d507ce5`; proof script SHA-256 `c36e2faebc16a6ab896864cfeee8989a4b9fdb87814688a393050be25a92c178`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c143691-exception-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C143691__LVMC-11-27-010-A__motor_vehicle_driver/native/prove_trail.py`. Hashes in fixtures remain placeholders; original exception evidence, Native capture, selected delivery paths and independent audit remain unfinished.

## Current-v2 exact primary Native construction checkpoint (2026-11-24)

`native/geometry.py`, `native/runner.py`, `native/tests/test_native.py` and `build-draft.py` now define two exact primary inline constructions in `draft-execution-manifest.json`. The acquisition draft authors a road lane and parallel trail lane, surveys both Native lanes, spawns two Native barrier props with a measured vehicle-clear gap, and varies only the requested lateral route. It retains 600 original pose/body/control rows at 20 Hz and four separate source-camera videos with Native frame joins. The `streetbarrier` blueprint and physical passage have not been verified on a server. Both exact primary bundles passed pinned current-v2 `runtime.py offline`. The receipt `current-v2-primary-offline-checkpoint.json` has SHA-256 `c2873cef5b9424895f1a187fdb7cf2c937b0920410c6fdbfb5d8dca4be0e3c42` and records exact commands, construction hashes and hashed logs.

From the physical repository root, export `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c143691-current-v2` and `PYTHONDONTWRITEBYTECODE=1`, then run `.venv-cpu/bin/python runtime.py preflight`, `.venv-cpu/bin/python work/training__C143691__LVMC-11-27-010-A__motor_vehicle_driver/build-draft.py`, and the receipt's offline commands. The source route and trail proofs still pass; the latter rejects 12 damaged sources. Scoped `.venv-cpu/bin/python worker_check.py --assignment training__C143691__LVMC-11-27-010-A__motor_vehicle_driver --complete` passes partial static checks.

Public compatibility on probe 1 returned nonzero at `KeyError: 'measurement_contract'`; no fixture or saved processing was reached. Next worker-owned CPU steps are the exact selected-requirement finalizer and runtime-format measurement contract, source-bound positive/negative fixture with all four camera streams, public compatibility, recorded-only process-saved, independent delivery/comparison audits, exception cases and tested risk-based fallbacks. The Native runner is an acquisition draft and still lacks a sealed `result.json`, source graph and owner-release output. Official trail-plan designation, City dedication, appropriate sign, motorized/exception identity and real barrier clearance need independent evidence; authored geometry and a prop name cannot establish them. Status remains partial.
