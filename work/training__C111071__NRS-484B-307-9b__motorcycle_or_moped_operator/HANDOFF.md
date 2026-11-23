# NRS-484B-307-9b at C111071

Actor: `motorcycle_or_moped_operator`. Frozen cell: `intersection` / `straight` / `inoperative_signal`.

Exact statutory source: NRS 484B.307(9)(b). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Failed-detection straight movement.

Controlled planning variable: `red_arrow_cycle_wait`. Proposed requests: stop before hierarchy boundary, wait two complete unchanged cycles, then proceed straight after yielding; proceed straight before two complete cycles. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: malfunction or nondetection proof; no prohibiting device; yield to pedestrians and lawful traffic; opposite-direction turn alternative.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

- Added `native/cycle_controller.py`, a measured-sample timing gate that derives complete applicable-device cycles from raw phase transitions after a ten-frame measured halt. It keeps the governing steady red/green-arrow state, detector command trace and pedestrian/traffic conflict check separate from any legal verdict. `native/construction-draft.json` records the fixed C111071 straight route, 600 frames at 20 Hz, four current-profile cameras and required raw Native acquisition. It remains unselected.
- `.venv-cpu/bin/python runtime.py preflight` exited 0. `.venv-cpu/bin/python native/prove_cycles.py` (from the assignment directory, or the full path in `result.json`) exited 0; the 600-frame synthetic positive enters after cycle-end frames 120 and 240, the controlled contrast enters after one, and six negative mutations reject missing frames, altered arrow, missing halt, serviced detector, pedestrian conflict and duplicate frame. Proof receipt: `native/cycle-controller-proof.json` SHA-256 486709b965a745e853a030fe5a082276d4aef0f22014f74383435dfbcd2b151e; log SHA-256 cc52b5f8cb587dd652629e40c33105bec66c587508b3243973e0e0a7a5c6a119. These are `synthetic_native_sample` diagnostics, not original Native observations.
- `.venv-cpu/bin/python worker_check.py --assignment training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator --complete` exited 0 for static package checks. Status stays `partial`.
- Next CPU work: integrate controller with an actual Native runner and four source-camera capture; derive stop hierarchy and cycle history from retained raw sources; build selected primary/fallback constructions and current-runtime offline, compatibility, process-saved and independent audit receipts. Physical signal causation, pixels, actor readback and legal judgment remain unverified.
