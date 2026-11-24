# NRS-484B-153-3 at C228817

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `load_unload` / `other_vehicle`.

Exact statutory source: NRS 484B.153(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Traffic-side door left open during loading or unloading.

Controlled planning variable: `traffic_side_door_open_duration`. Proposed requests: traffic-side door closes when immediate loading ends; same door remains open after immediate loading ends. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: passenger or cargo loading; traffic-side orientation; necessity duration unresolved.

Accepted membership: 4 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `native/controller.py` requests 600 frames at 20 Hz for the two planned probes, holding ego, passenger transfer, and passing path fixed while changing only the traffic-side door close frame (212 vs 400). This is a CPU policy request; Native actuator wiring and original observations are still required.

`native/measure_door.py` joins contiguous Native frame/time, four source-camera identities, door side and state, selected driver responsibility, passing-vehicle trajectory, stationary ego, and sourced passenger occupancy/pedestrian or cargo transfer. It reports elapsed and post-transfer open time while keeping necessity and immediacy unresolved. Synthetic proof: 3 positive diagnostic variants and 11 negative source/geometry rejections. No synthetic sample establishes legal or physical acceptance.

SHA-256 bindings:

- `native/controller.py`: `cee33d963d4683e1974534c618852cd7b0b87f3ef6406b0e058c0642306bd79a`
- `native/measure_door.py`: `0898bb6f11d658262faac3ac3e6c77166e0647fb9e31fa5fd4b7219ab1eac86e`
- `native/prove_door.py`: `7cbd62f088715883f67b2fdf5807c8fa9ab8ad6ee147541e47a8a7f28f66898d`
- `native/door-proof.json`: `7ba6c21cfa29a2653261c74d0c8bd7907af079515451f1e54e6772201de23138`
- `native/measurement-contract.json`: `d2e6b2ddd5a59ed5ad78986742f372f8b4753b46b6683cf5f76f6b6ab0eeba6f`

Remaining CPU work: exact Native construction and door actuation/capture wiring, four distinct source-preserving candidates where required, offline/compatibility and saved-only proofs, semantic proposal and independent audits, branch/evidence review and comparison. Accepted membership remains metadata only without original source-hashed equivalence. Keep partial until scoped strict delivery gate passes.

## 2026-11-23 independent comparison checkpoint

`native/audit_comparison.py` independently measures both 600-frame trace envelopes and rejects changes to road, actor, passing-vehicle start, transfer event, camera policy, door side, and source identity. It reports the measured door-close difference while leaving necessity and immediacy unresolved. The diagnostic pair measured a 9.4 s difference and rejected eight altered-source or altered-control comparisons. The CLI requires external SHA-256 bindings for both packet files. This is source-shaped CPU proof only; original Native packets and source-camera video have not been captured.

The `case-plan.json` now maps all six source observation terms to explicit Native trace fields and records the independent comparison command and proof hashes. The mapping still needs original Native capture and pixel review.

Command: `.venv-cpu/bin/python work/training__C228817__NRS-484B-153-3__motor_vehicle_driver/native/prove_comparison.py` (exit 0). Scoped checkpoint: `.venv-cpu/bin/python worker_check.py --assignment training__C228817__NRS-484B-153-3__motor_vehicle_driver --complete` (exit 0, static checks passed).

Hashes: `native/audit_comparison.py` 4493ca4a7e514217c3a1ac8e5ab6b7ac1e5c796fea7076d973f60be61efeb0e8; `native/comparison-proof.json` bc3010782f9fedb1aea2e62c45c393710e19ac5bfbe00d4a7754766359c65913; `native/comparison-proof.log` 6180978d15d828c153b23bfff5e32749d7da9de79d0e3e11d3d50fe27647ad45.

Next CPU work: wire an exact CARLA/OpenDRIVE scene and door actuator with source-camera capture into the frozen runtime, then test one primary through offline, compatibility and process-saved before expanding to distinct fallbacks and independent delivery audits. Preserve the four historical accepted recording IDs as membership context until source-hashed equivalence is available. Status remains partial.
