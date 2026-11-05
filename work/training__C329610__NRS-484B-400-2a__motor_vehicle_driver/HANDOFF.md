# NRS-484B-400-2a at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Exact source: NRS 484B.400(2)(a). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Left-turn approach between two-directional highways..

Controlled variable: `approach-lane lateral position`. Requested pair: approach left turn near centerline in right half; approach left turn away from centerline in right half. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 2. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 4; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Blocker: Draft Native construction and eight exact offline receipts exist, but pinned-runtime positive/negative compatibility recipes, physical-preparation fixtures, independent delivery acceptance, saved Core processing and full comparison audits remain unproved. The frozen semantic checker also reads `law` instead of the input's `law_record`.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Both intersecting highways must be two-directional. Measure approach path in the right half nearest centerline before the left turn; the turn exit is not the target.

## Current source and measurement review

The two witness labels describe the same NRS 484B.400(2)(a) clause; the duplicate was removed from requirement dispositions. The plan now has a time scoped measurement contract draft, exact activation facts, required Native geometry and controller evidence, and three measurable candidate risks. This remains a draft. No selected delivery manifest, positive/negative compatibility proof, independent delivery audit, or CARLA observation exists. The result remains blocked.

## CPU geometry continuation, 2026-11-05

`native/geometry.py` now authors a two-way orthogonal intersection with two lanes in each direction, a centerline, both left-turn connector links, and controlled approach positions at -1.75 m and -5.25 m. Its CPU check passed XML/link inspection, 0.3 m maximum route-sample spacing, pavement containment, and a prospective 5.2 m by 2.2 m body proxy for both paths. The command, source hash, and log hash are recorded in `case-plan.json` and `result.json`. Generated map and route samples are in ignored `.runtime-work/c329610-geometry-20261105`.

The initial geometry check is an offline proposal. Native map loading, actual asset footprint, route completion, exact compatibility, independent delivery audits, and physical camera evidence remain unverified. The selected case count remains zero and the result remains blocked. The later draft bundles and their CPU proofs are summarized below.

The case plan also has a 20 Hz, 24 s synchronized four-view capture proposal and explicit Native/source-packet mappings for all eight source observation terms. The camera poses, duration sufficiency and packet production remain untested. The Native-frame geometry prototype accepts only time ordered samples with a surveyed two-way geometry hash; its positive and five adversarial unit tests pass. A saved-only finalizer now exercises that measurement in a synthetic local fixture, but a full Core processing receipt is absent.

## Draft delivery bundle continuation

The package now has a Native runner proposal, an observed-pose path controller, four camera policies, a saved-only finalizer, and five validated semantic stage drafts. Two case IDs each have a primary and three distinct fallback construction bundles. All eight exact bundles pass `runtime.py offline` with fifteen unit tests per bundle. The independent draft audit checks construction/log hashes and source equality; a controlled-input audit checks held variables across the pair. The source-hashed measurement contracts validate. A four-frame synthetic local fixture passes saved finalization, the Native attempt validator, four source-video decodes, and missing-source negative checks for both case IDs; the validator correctly reports `rebuild_required: true`. These drafts are unselected and do not establish CARLA physical feasibility, exact runtime compatibility, independent delivery acceptance, or a saved Core trace for either case. `result.json` remains `blocked` with selected candidate count zero.

The pinned `semantic_delivery.validate` reads `assignment["law"]`, but the frozen assignment has `law_record` and no `law`. The exact failing input/command/log and a passing in-memory alias diagnostic are recorded in `work/_shared/frozen-semantic-checker-defect.json`. Do not edit the frozen input or runtime to bypass it.

The static checker prohibits generated diagnostic paths beginning `offline-` under `work/`. The per-candidate retained logs and receipts are now named `draft-command.log` and `draft-receipt.json`; `run-draft-offline.py` uses those names. The eight-bundle audit and static checker pass after the rename. A separate attempt to run the small synthetic fixture through the pinned Core converter stopped at missing `capture/native/frames.jsonl`. Finish a complete synthetic Native-shaped capture, then rerun Core processing/render, fixture recipes and positive/negative compatibility for each exact candidate. This is worker-owned fixture work, not an external blocker.
