# training__C135709__NRS-484B-517__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.517. Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

signed stand occupied versus unoccupied by non-taxicab. Compare only `taxicab_stand_occupancy_by_nontaxicab` (bool) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Blocker and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

## Update 049: current-input CPU continuation

The current frozen `inputs/training__C135709__NRS-484B-517__motor_vehicle_driver/assignment.json` is bound by `result.json.input_sha256=2bbe8070075891f80354cc60982822ad2479fd22a62beb3bcb301ffc0f4c8450`. The old `law_record` reads in work-owned `native/check.py`, `native/build_statutory.py`, and `native/audit_statutory.py` were changed to canonical `law`. `native/build.py`, `native/build_saved.py`, and `build_offline.py` rebuilt the eight reference/contrast primary and three fallback requests against that exact input. Previous proof receipts were retained as `update049-historical-*`; they do not qualify the rebuilt sources.

`native/capture.py` now requests the four named source cameras: overview 1920x1080, approach, reference_corner, driver_reference each 1280x720, synchronized at 20 Hz. `native/prepare_raw.py` requires all four lossless original streams, while `--synthetic-cpu` remains an explicitly diagnostic raw-to-saved path. No CARLA capture was run. This code path still needs canonical selected packaging and runtime processing proof.

Replayed `.venv-cpu/bin/python work/training__C135709__NRS-484B-517__motor_vehicle_driver/prove_compatibility.py` with 8 request positives, 32 changed-source negatives, 24 synthetic saved/raw-to-saved positives, and 32 saved negatives. `update049-compatibility.log` and `offline/proof-compatibility.json` record this. Independent `.venv-cpu/bin/python work/training__C135709__NRS-484B-517__motor_vehicle_driver/audit_package.py` checked eight copied bundles, 1920 requested and 1920 saved rows, and replayed the altered-source rejections; `offline/package-audit.json` SHA-256 is `ee66b14b369e43678b54e9e4c7e6a002525e7500263e3e6b50480e950024aabe`. Saved comparison and statutory audits passed for the reference/contrast pair; `native/comparison-audit.json` SHA-256 is `b83ae7b9bf8b090f4b3400d86cb16fa9c1fd4aee0b513a1c022b94704abcaf09`, and `statutory-audit.json` SHA-256 is `e6d3f7fd23a484827c2e703279f56b6d6a6818b256682e50711aa971fd4dfa8a`. All invented measurements are synthetic CPU diagnostics, with no legal verdict or accepted original.

`build-semantic-foundation.py` validated draft relevance, exact-law template, three judgment-observable drafts, and binding stages; `proposals/semantic-foundation-proof.json` SHA-256 is `8f240f447a78b9b2ca41a0cbee1d1348681dabd2c6fb40ecb94d46a96137e10b`. Judgment calls retain official signing, expeditious passenger loading, and noninterference as unresolved. The draft cases stage and complete semantic index are not authored yet.

The checkpoint command `.venv-cpu/bin/python worker_check.py --assignment training__C135709__NRS-484B-517__motor_vehicle_driver --complete` passed in `update049-scoped-complete.log`. The same command with `--require-delivery-ready` fails truthfully with `Preparation acceptance failed: partial/missing packages remain` in `update049-scoped-strict.log`. `result.json` is `partial`, not ready.

Next CPU work on this assignment: complete the canonical cases stage including the required judgment-sweep plan and exact reference/contrast comparison; select both cases without claiming their physical outcome; package the selected runner, four-source capture, finalizer, measurement contracts and three distinct fallback constructions; generate source-hashed four-stream diagnostic recipes; run pinned-runtime exact offline, actual saved processing, positive and missing-source compatibility for primary and all fallbacks; implement and test independent physical, delivery and comparison audits; bind receipts in `execution-manifest.json`; then run the scoped strict gate. Independently review the exact statute, especially official designation/signing and the passenger exception, before readiness. Actual CARLA motion, sign visibility, parking, passenger activity, and legal adjudication remain future physical review, never CPU fixture claims. These missing package and proof implementations are worker-owned CPU work, not an external dependency.

Update 049 continuation: the same work-owned semantic builder now also validates `proposals/cases.json` with a neutral baseline, the reference/contrast controlled pair, and an explicitly incomplete qualitative judgment-sweep plan. `proposals/semantic-index.json` binds all six canonical stage types. Latest `proposals/semantic-foundation-proof.json` SHA-256 is `84a502357587256f2c8709bbf330e87a17dff9571097809d4992ca28037d06b2`. The earlier sentence saying the cases stage is not authored is superseded. This is draft semantic preparation; selected construction and pinned-runtime proofs are still absent. The assignment-scoped non-strict check passed again after these stage additions.

The update 049 complete-batch strict rerun failed before package acceptance on `ValueError: Unapproved output: runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` (`work/_shared/update049-full-strict.log`, SHA-256 `703ba86fdbd66d9b2589e7394601c6fea6837a3ee9a75481eea27a5d0f91c2fa`). This generated out-of-work file is separate from the assignment's unfinished CPU deliverables; neither issue makes C135709 ready.
