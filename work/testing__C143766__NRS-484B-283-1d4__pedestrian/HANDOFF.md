# C143766 NRS 484B.283(1)(d)(4) pedestrian delivery preparation

Status: CPU delivery prepared on the pinned runtime. The exact assignment gate passes. Original physical crossing and legal conclusions remain unverified.

## Frozen source and branch coverage

The exact law in `inputs/testing__C143766__NRS-484B-283-1d4__pedestrian/assignment.json` governs an illuminated steady Don't Walk, Wait or upraised-hand indication. It prohibits a new pedestrian crossing entry while allowing a pedestrian who entered lawfully under subparagraph (1) or (2) to continue toward a curb, sidewalk, provided safety zone or other place of safety as soon as possible, subject to introductory exceptions in NRS 484B.287, .290 and .350. The assigned C143766 nonmotorized-trail/travel/sidewalk cell supports a conditional crossing scene only after original connected trail, highway, signal and sidewalk sources are reviewed. `evidence.json` lists zero accepted recordings, so no reuse is asserted. The exact law/actor has no training judgment-range entry and no numeric legal cutoff is proposed.

Every selected case ID has prefix `testing__C143766__NRS-484B-283-1d4__pedestrian__`:

| Suffix | First highway entry | Destination | Arrival | Role |
| --- | --- | --- | --- | --- |
| `walk_entry_sidewalk_before` | Walk | sidewalk | flashing | antecedent timing reference |
| `walk_entry_sidewalk_after` | Walk | sidewalk | steady | selected continuation reference |
| `steady_new_entry` | steady | sidewalk | steady | prohibited new-entry probe |
| `walk_entry_curb_after` | Walk | curb | steady | destination alternative |
| `walk_entry_safety_zone_after` | Walk | provided safety zone | steady | destination alternative |
| `walk_entry_other_place_after` | Walk | reviewed other safety place | steady | destination alternative |
| `countdown_entry_sidewalk_after` | flashing with countdown | sidewalk | steady | prior-entry basis under subparagraph (2) pending source review |

`case-plan.json` maps all three selected requirements to these cases and declares six controlled comparisons: `arrival_before_steady`, `entry_phase`, `curb_destination`, `safety_zone_destination`, `other_place_destination`, and `prior_entry_basis`. The comparisons retain source/site, actor, signal and 20 Hz four-camera conditions except their declared entry, arrival or destination differences. `prior_entry_basis` changes entry phase and countdown together because the legal dependency is a different prior-entry signal provision. No case asserts that an observed prior phase establishes lawful entry, that an observed endpoint is legally safe, or that a chosen elapsed time meets “as soon as possible.” Original position and time histories retain movement, pauses and reversals for independent review; physical constraints and opening-exception applicability require sourced local review. The intro clause is retained in `proposals/template.json`.

## Construction and audits

`pedestrian_crossing.py` requires separately sourced connected trail, crossing, highway polygon, accessible sidewalk, facing signal and all four destination routes. `reviewed_site.py` rejects an absent or stale original OpenDRIVE/source packet before Native world mutation. `runner.py`, `native_entry.py` and `analysis.py` implement selected 900-frame acquisition, world restoration, original signal and pedestrian readbacks, exact frame joins, four FFV1 views, and saved finalization. The local operator supplies `C143766_CROSSING_REVIEW_PACKET`, `C143766_CROSSING_SOURCE_ROOT` and `C143766_CROSSING_ADAPTER_MODULE`; the adapter must implement `validate_review`, `configure`, `sample` and `teardown`. Physical realization of requested phases and routes remains to be established. `delivery_audit.py` independently rejects missing original source and checks participants, joins and four full video decodes. `comparison_audit.py` rejects undeclared changes and missing source. Each selected case has a physical-risk assessment and a `fallback1` speed adjustment from 1.2 to 0.8 m/s on the same reviewed route, signal and capture profile, selected only after primary path or camera failure. `execution-manifest.json` binds exact constructions, receipts, saved-only processing and independent audit commands. `gpu-queue-proposal.json` supplies the seven local jobs and six comparison audit commands for lead integration.

## Reproduce CPU proofs

From repository root set `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c143766-1d4-owner-nov26/output"`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH="$PWD/work/testing__C143766__NRS-484B-283-1d4__pedestrian"` before direct runtime imports. Temporary fixture material stays under `.runtime-work/`.

- `.venv-cpu/bin/python -m unittest discover -s work/testing__C143766__NRS-484B-283-1d4__pedestrian/tests -v`: five source/geometry/measurement tests pass; `cpu-tests.log`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/prove_offline.py`: fourteen exact primary/fallback construction proofs; `cpu-offline-proofs.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/prove_compatibility.py`: fourteen positive and missing-source negative compatibility proofs through finalizer, validator, converter, Lean decoder, renderer and full video decoder; `cpu-compatibility-proofs.json`. Nine-frame media are synthetic fixtures.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/prove_saved.py`: seven recorded-only checks; `cpu-saved-proofs.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/prove_independent.py` and `prove_comparisons.py`: seven delivery positive/negative pairs and six comparison positive/negative pairs; `cpu-independent-proofs.json`, `cpu-comparison-proofs.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/prove_physical.py` and `prove_runtime_physical.py`: source/lifecycle and current-runtime complete/incomplete/missing motion fixtures; `physical-preparation.json` per case and `cpu-runtime-physical-proof.json`.
- `.venv-cpu/bin/python work/testing__C143766__NRS-484B-283-1d4__pedestrian/validate_selected.py`: selected manifest, semantic stages, handoffs and receipts pass; `cpu-current-validators.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C143766__NRS-484B-283-1d4__pedestrian --complete --require-delivery-ready`: exit 0.

The local operator must review the original source packet and signal symbol/illumination, run CARLA, confirm actual pedestrian movement and camera pixels, independently audit original bytes, and obtain legal/context review of prior entry, promptness, destinations and exceptions before canonical acceptance to full-test.
