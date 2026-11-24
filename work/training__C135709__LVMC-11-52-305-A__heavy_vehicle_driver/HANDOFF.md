# LVMC-11-52-305-A at C135709

Actor: `heavy_vehicle_driver`. Frozen cell: `narrow_road` / `park` / `parking_restriction_device`.

Exact statutory source: LVMC 11.52.305(A); with 11.52.305(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Covered commercial vehicle parked beside a public park.

Controlled planning variable: `covered_vehicle_parking_adjacency`. Proposed requests: covered commercial vehicle parks away from protected adjacency; same covered vehicle parks beside public park. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: posted sign permission; residence district 300-foot definition; public school; loading/delivery exception; essential local service exception; 24-foot length or 8000-pound weight.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/controller.py` now gives both park-frontage probes the same 600-frame / 20 Hz feedback policy, changing only the requested station. Its source-shaped CPU proof, `native/controller-proof.json` (SHA-256 `a7396c10bee0f2d59ccbc35435a0056c0b4ab83c7e80743e069e8d15fd469fe0`), passes two positive targets and rejects movement during the hold, the wrong frontage station and a shortened trace. The synthetic trajectory only tests controller and validation logic; it is not original CARLA motion.

`native/measure_parking.py` and `native/measurement-contract.json` define the saved-source join for original Native frame identities, four source-camera identities, observed speed and footprint, the surveyed street/park boundary, external public-park status and commercial vehicle specifications. The 600-frame CPU proof, `native/parking-proof.json` (SHA-256 `1e9659def0715092961e269f17b3df4e927a640c213fe7671a85f3d2177dd795`), distinguishes parking away from versus beside the park frontage and rejects eight source/frame/geometry defects. Fixture source hashes are placeholders and do not establish original provenance, actual park status, physical adjacency or any legal outcome.

Pinned `.venv-cpu/bin/python runtime.py preflight` and assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment training__C135709__LVMC-11-52-305-A__heavy_vehicle_driver --complete` both pass as partial-package checks. Next CPU work: build the actual CARLA capture runner and exact four-camera constructions, source the public-park and commercial-vehicle facts, add posted-permission/loading/service exception cases and measurements, then run exact offline, compatibility, saved-only and independent delivery/comparison proofs. The package remains `partial`.

## 2026-11-23 size and weight branch CPU checkpoint

The parking meter now reports the statute’s independent vehicle thresholds: overall length at least 24 feet (`7.3152 m`) and unladen mass in excess of 8,000 pounds (`3628.73896 kg`). Four source-shaped cases test length only at the inclusive length boundary, weight only above the strict mass boundary, neither, and both. All eight existing damaged-source checks still reject. `native/parking-proof.json` SHA-256 `3636c002471b6b23680fc4b4f3f7ba541b9a75c81cb3610301d0251bc1cf3043`; meter SHA-256 `8d8b494100e91ca0cc6f975c0e6428b3986e7d798d5a7c951f49d4b1f6b87ceb`; proof script SHA-256 `888ddf66ca727fe2082b3209738768689e5343d6715239207b2fd528330138db`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c135709-size-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C135709__LVMC-11-52-305-A__heavy_vehicle_driver/native/prove_parking.py`. This is a numeric source-shaped software check only; original vehicle specifications, public-park adjacency, permission and loading/service exceptions, exact Native construction and selected delivery proofs remain unfinished.

## Current-v2 exact primary Native construction checkpoint (2026-11-24)

`native/geometry.py`, `native/runner.py`, `native/tests/test_native.py` and `build-draft.py` now define exact primary inline constructions for the two selected cases in `draft-execution-manifest.json`. The Native draft uses the same feedback controller for both station requests, surveys the narrow-road lane, retains original pose, velocity, body extent, controller request and frame identities for 600 frames at 20 Hz, and retains four separate source-camera streams. Both primary bundles passed pinned current-v2 `runtime.py offline`. `current-v2-primary-offline-checkpoint.json` has SHA-256 `ad3e3c93c1a91c974db1fb390cbd7b243c0ca42e8562566d12435fcefafbdeb4` and contains exact commands, construction hashes and hashed logs.

From the physical repository root, export `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c135709-current-v2` and `PYTHONDONTWRITEBYTECODE=1`, then run `.venv-cpu/bin/python runtime.py preflight`, `.venv-cpu/bin/python work/training__C135709__LVMC-11-52-305-A__heavy_vehicle_driver/build-draft.py`, and the receipt's offline commands. Controller and parking source proofs still pass (three and eight negative checks). Scoped `.venv-cpu/bin/python worker_check.py --assignment training__C135709__LVMC-11-52-305-A__heavy_vehicle_driver --complete` passes partial static checks.

Public compatibility on probe 1 returned nonzero at `KeyError: 'measurement_contract'`; no fixture or saved processing was reached. Next worker-owned CPU steps are an exact selected-requirement finalizer and runtime-format measurement contract, source-bound positive/negative fixture with all four camera streams, public compatibility, recorded-only process-saved, independent delivery/comparison audits and tested risk-based fallback constructions. The runner deliberately leaves public-park designation, posted permission, commercial vehicle class and vehicle specifications unsourced. A generic vehicle blueprint and authored boundary do not establish those statutory facts; the parked vehicle and visible park frontage also need physical inspection. Status remains partial.

The current Native runner is an acquisition draft: it does not yet emit the required sealed `result.json`, source graph capture, or owner-release receipt. Those are additional worker-owned capture/lifecycle steps before `runtime.py capture` can yield a process-saved attempt; the offline check validates only static code and tests.
