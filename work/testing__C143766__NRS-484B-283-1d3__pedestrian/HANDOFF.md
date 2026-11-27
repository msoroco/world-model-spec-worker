# C143766 NRS 484B.283(1)(d)(3) pedestrian delivery preparation

Status: CPU delivery prepared on the current pinned runtime. The exact assignment gate passed. No physical crossing, legal outcome or canonical acceptance is claimed.

## Frozen scope and evidence

- Assignment: `testing__C143766__NRS-484B-283-1d3__pedestrian`; full-test target; C143766 nonmotorized-trail, highway crossing and sidewalk context.
- Frozen branch: continuation toward sidewalk conditional on lawful prior entry. `inputs/testing__C143766__NRS-484B-283-1d3__pedestrian/assignment.json` contains the exact law. `case-plan.json` preserves the source witness and separately identifies the flashing no-countdown new-entry prohibition, conditional continuation before steady, four named destinations, countdown condition and NRS 484B.287, .290 and .350 exceptions.
- Frozen accepted-evidence inventory contains zero recordings. The exact law/actor has no judgment-range entry; no numeric legal cutoff was invented. An observed Walk-phase entry is not proof of lawful entry under subparagraph (1). Exception applicability and whether a place is legally safe remain independent review questions.

## Exact selected cases and comparisons

| Case suffix | Entry | Destination | Arrival | Flashing countdown |
| --- | --- | --- | --- | --- |
| `walk_entry_sidewalk_before` | Walk | sidewalk | before steady | absent |
| `walk_entry_sidewalk_after` | Walk | sidewalk | steady | absent |
| `flashing_new_entry` | flashing | sidewalk | before steady | absent |
| `walk_entry_curb_before` | Walk | curb | before steady | absent |
| `walk_entry_safety_zone_before` | Walk | provided safety zone | before steady | absent |
| `walk_entry_other_place_before` | Walk | reviewed other safety place | before steady | absent |
| `countdown_present` | Walk | sidewalk | before steady | present |

Every full case ID is the assignment ID followed by `__` and the suffix. `case-plan.json` names six exact comparisons: `arrival_before_steady`, `entry_phase`, `curb_destination`, `safety_zone_destination`, `other_place_destination`, and `countdown_activation`. Each declares fixed source/site/capture conditions and its single intended change. The destination comparisons use distinct selected destination route requests; the diagnostic fixture proves audit logic, while physical endpoint separation awaits original capture.

## Construction, capture and saved sources

`pedestrian_crossing.py` validates separately sourced trail, highway polygon, crossing, accessible sidewalk, facing official signal and connected candidate destination routes. Its constructor requests a 20 Hz pedestrian route and Walk/flashing/steady schedule through a CARLA-lazy adapter; focused tests cover all seven requests and missing/disconnected sources. `reviewed_site.py` requires a separately reviewed, source-hashed original OpenDRIVE packet with those features and cited exception context before Native world mutation. `runner.py` and `native_entry.py` provide the selected 900-frame, 45-second, four-camera Native handoff, exact frame map, same-frame original signal/pedestrian samples, encoder closure, source receipt and world restoration. The operator must supply `C143766_CROSSING_REVIEW_PACKET`, `C143766_CROSSING_SOURCE_ROOT`, and `C143766_CROSSING_ADAPTER_MODULE`; the adapter protocol requires `validate_review`, `configure`, `sample`, and `teardown`, with original signal and pose readbacks. `runner.py --check` is source-free; actual capture rejects missing reviewed inputs.

`crossing_measurement.py` verifies source identities, original 20 Hz order, signal transitions, first highway entry, destination arrival, steady onset and countdown. `analysis.py` binds the source/receipt hashes, trace/frame/camera joins, selected case variables and three case-specific selected-requirement measurements. It writes Native-shaped result/evidence streams and a saved analysis report while leaving legal findings unresolved. `delivery_audit.py` independently rechecks the original packet, selected variables, all participants, time joins and full four-view decode; `comparison_audit.py` independently rejects missing source and undeclared contrast changes. The selected `execution-manifest.json` binds exact construction hashes and positive/negative receipts. `gpu-queue-proposal.json` has seven exact local jobs and six comparison commands; the lead owns shared queue integration.

Each case has a specific physical-risk assessment. `fallback1` changes only walker speed from 1.2 to 0.8 m/s on the same reviewed site, route, law, actors, signal, 45-second 20 Hz duration and four cameras if the primary path or camera coverage fails. It is a candidate for the same case, never an additional recording or a desired legal outcome.

## CPU proof commands and outcome

From the repository root, set `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c143766-1d3-owner-nov26/output"` and `PYTHONDONTWRITEBYTECODE=1` before direct runtime imports or proof scripts. All temporary fixtures and outputs belong under `.runtime-work/`.

- `PYTHONPATH=work/testing__C143766__NRS-484B-283-1d3__pedestrian .venv-cpu/bin/python -m unittest discover -s work/testing__C143766__NRS-484B-283-1d3__pedestrian/tests -v`: five tests pass; `cpu-final-tests.log`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/prove_offline.py`: fourteen primary/fallback exact constructions pass; `cpu-offline-proofs.json` and case logs.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/prove_compatibility.py`: fourteen positive/negative source checks pass through the pinned finalizer, Native validator, converter, Lean decoder, renderer and full video decoder; `cpu-compatibility-proofs.json` and case receipts. The diagnostic 9-frame videos are synthetic software fixtures, not original recordings.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/prove_saved.py`: seven recorded-only processing checks pass; `cpu-saved-proofs.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/prove_independent.py` and `prove_comparisons.py`: seven delivery positive/missing-source negative pairs and six comparison positive/missing-source negative pairs pass; `cpu-independent-proofs.json` and `cpu-comparison-proofs.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/prove_physical.py` and `prove_runtime_physical.py`: seven source/lifecycle fixtures and current-runtime motion criterion complete/incomplete/missing branches pass; `physical-preparation.json` per case and `cpu-runtime-physical-proof.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d3__pedestrian/validate_selected.py`: selected manifest, semantic stages, delivery handoffs and receipt bindings pass; `cpu-current-validators.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C143766__NRS-484B-283-1d3__pedestrian --complete --require-delivery-ready`: exit 0 on the pinned runtime.

## Local continuation

Review the original site and independent legal context, then prepare the exact candidate. A physical CARLA run must demonstrate that the trail and crossing connect, the selected destination and official facing display exist and are visible in the original four cameras, the signal actually flashes without countdown where required, and the walker crosses/arrives at the measured original frames. The independent original-source and delivery audits must review those bytes before canonical acceptance into full-test. The source-gated adapter interface is a local integration dependency, not evidence that CARLA can physically realize any requested signal or path.
