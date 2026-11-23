# NRS-484B-307-9a at C111603

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `turn` / `other_vehicle`.

Exact statutory source: NRS 484B.307(9)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Turn with other intersection traffic. Planned comparison variable: `arrow_only_movement`. Requests: driver follows illuminated arrow movement; driver takes a movement different from the illuminated arrow. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: a steady red with a green turn arrow faces the subject; the subject enters the intersection.

Timing to retain: the permission lasts only while the arrow is illuminated; entering for any movement other than the arrow's is the violation, at the moment the path departs from it.

Exceptions and numeric alternatives planned: the two-cycle exception for motorcycles, mopeds and cycles the text cites.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Native CPU construction: `native/build.py` authors eight unselected source-pinned 600-frame/30-second requests across two controlled movements and four policies (primary, slower approach, elevated overview, two-second pre-approach dwell plus five-second yield hold). It now binds the current frozen assignment SHA `dec45d9a59caf5589820a4f2a20e69857706b6dfad4f27b03d1d5c17c6152e8a` and current numbered `law.text`. `native/prove_request.py` passes eight exact positives and 40 changed-source/signal/actor/blueprint negatives. `native/saved.py` processes 4,800 explicitly synthetic frame joins and `native/prove_saved.py` passes eight positives and 48 altered-source/frame/actor/signal negatives. `native/audit_request.py` independently checks all requested and synthetic saved rows plus four controlled movement pairs. `native/measurement-contract.json` identifies the original channels needed for each mandatory source observation. The steady red plus green arrow, other vehicle and yield interval are requested targets, not original observations. The three fallback switches have distinct requested changes. `native/prove_fallback_quality.py` measures authored speed and signal-to-entry timing and proves three synthetic trigger decisions (6 positives/8 negatives); an independent audit recomputes all eight measurements; original capture-quality triggers remain unmeasured.

Current pinned offline compatibility: `native/build_offline.py` pins eight unselected constructions with `native/capture.py` as their entrypoint. All eight pass the current `runtime.py offline` with 56 CPU tests and no simulation. `native/audit_offline.py` checks 120 materialized file bytes and rejects a changed construction digest. The capture entrypoint's CPU `--check` path passes eight source-bound positives and eight altered-blueprint negatives. Original CARLA capture has not run. The code requires two distinct generated signal actors, physical ego and other vehicles, synchronized 600-frame actor/video streams, four source cameras named `overview`, `approach`, `reference_corner`, `driver_reference`, FFV1 media and world restoration; it does not claim the generated green actor visibly renders a directional arrow.

Original saved-processing CPU path: `native/process_original.py` validates exact source and generated map readback, two continuous physical actor identities and bodies, 600 synchronized actor/video rows, steady red plus green Native actor states, four decoded FFV1 streams in original mode, capture/restoration receipt and source-hashed review. It measures actual heading change, movement match and speed during the requested yield hold, leaving legal verdict null. Its explicitly synthetic source-shape fixtures pass eight positives and 72 altered actor/frame/body/lane/signal/media/review negatives; four controlled movement pairs retain a 90-degree versus zero-degree heading distinction. Marker media is refused in original mode. No original media or visual review has run.

Capture-bound fallback quality: `native/fallback_quality.py` now invokes the source-bound original processor before measuring physical approach speed, physical hold-to-entry time and source-hashed reviewed visibility frames. Its synthetic source-shape proof passes two positives and ten material negatives, including refusal to accept marker media as original. Original capture and human frame review have not run.

Current CPU receipt: `.venv-cpu/bin/python work/training__C111603__NRS-484B-307-9a__motor_vehicle_driver/native/prove_current_runtime.py` rebuilt the eight drafts and ran 13 construction, saved, offline, negative, and independent audit steps, all exit 0. The command logs and hashes are in `native/current-runtime-proof.json` (SHA recorded there for each underlying receipt). `.venv-cpu/bin/python runtime.py preflight` and `.venv-cpu/bin/python worker_check.py --assignment training__C111603__NRS-484B-307-9a__motor_vehicle_driver --complete` both exited 0. This is an implementation checkpoint, not delivery readiness.

Remaining CPU work: select exact cases only after source and branch review; migrate the drafts to current selected `execution-manifest.json` and `runtime.py compatibility` / `process-saved` paths with source packets, canonical frame map, composed video, required atom mapping, selected positive/negative tests, independent delivery and comparison audits, and semantic proposals. All four-corner signal and pedestrian/crosswalk acquisition terms remain to be implemented as retained raw sources. Original Native execution compatibility, directional-arrow pixels, original measured fallback triggers, original saved processing from actual media, legal yielding and cited two-cycle exception applicability remain unverified. The assignment stays partial and unselected.

Resume: finish the selected current-runtime CPU path and run the assignment-scoped strict gate before any ready label. Local GPU execution will later measure the original physical sources and pixels.
