# NRS-484B-210-1 at C146314

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_multilane` / `overtake_right` / `other_vehicle`.

Exact statutory source: NRS 484B.210(1); with 484B.210(4). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Paragraph (d). Planned comparison variable: `passing_right_permission`. Requests: driver passes right on unobstructed wide one-way pavement; driver passes right where required pavement condition fails. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject overtakes and passes another vehicle on its right.

Timing to retain: the 200-foot condition is measured over the whole excursion into the unmarked pavement, so the trace must cover entry and return; the permitting condition must hold for the whole pass, not only at its start.

Exceptions and numeric alternatives planned: the overtaken driver is making or signalling a left turn; unobstructed pavement, free of parked vehicles, wide enough for two or more lines in each direction; unmarked pavement, free of parked vehicles, where the pass covers no more than 200 feet and crosses no intersection or private way; a highway restricted to one direction, unobstructed and wide enough for two or more lines; the 200-foot limit does not bind an authorized emergency vehicle, a permitted emergency vehicle, a traffic incident management vehicle, a tow car, a coroner vehicle, or a transit bus using a shoulder where signage allows it; unmarked pavement right-pass excursion numeric boundary 200 feet.

Unresolved judgment or rule composition: the permit-based exemptions cite provisions outside the corpus and are not observable from a scene. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 current paragraph (d) primary construction

The 600-frame, 20 Hz, four-camera primary request for `__witness_1` now builds from `native/build_current_primary.py` into `native/current-primary/`. `native/current_primary_capture.py` implements a lazy CARLA capture for the four named camera sensors, requested steering targets, retained actor poses, frame joins, and 30-second duration. No CARLA was run; requested motion, geometry, and policy remain unobserved. The source checker now rejects a rehashed but mismatched assignment identity.

Pinned CPU preflight passed: `.venv-cpu/bin/python runtime.py preflight`. Exact pinned offline materialization and tests passed using `.venv-cpu/bin/python runtime.py offline --manifest work/training__C146314__NRS-484B-210-1__motor_vehicle_driver/native/current-primary/manifest.json --case training__C146314__NRS-484B-210-1__motor_vehicle_driver__witness_1 --output .runtime-work/c146314-210-1-witness1-primary-offline3`. The exact source and log hashes are in `native/current-primary-offline-proof.json`; `native/current-primary-offline.log` is the copied runner log. This is an unselected construction and offline software proof only.

Next CPU work: select the exact paragraph (d) pair only after a complete source review and measurements mapping; provide a source-hashed diagnostic recipe with four generated camera videos; derive observations from retained Native-shaped raw sources in a saved finalizer; run pinned positive and missing-source negative compatibility, actual `process-saved`, three engineering fallbacks and controlled comparison audits; then complete the other statutory branches, semantic proposals and independent acceptance proofs. The current copied 240-frame two-camera paragraph bundles are historical diagnostics, not these current-runtime proofs. Keep `result.json` partial until assignment-scoped strict delivery passes.

Scoped checkpoint: `.venv-cpu/bin/python worker_check.py --assignment training__C146314__NRS-484B-210-1__motor_vehicle_driver --complete` exited 0. The same command with `--require-delivery-ready` exited 1 because result remains partial; log `native/current-primary-strict.log` SHA-256 `4b7c473100b0567da2a85548669f3b674e506ee243d68a01763fb24c3c8a61e2`. The returned assignment has 1,165 files, none above 2 MiB or with trailing whitespace/conflict markers in text files.
