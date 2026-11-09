# NRS-484B-307-9a at C111603

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `turn` / `other_vehicle`.

Exact statutory source: NRS 484B.307(9)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Turn with other intersection traffic. Planned comparison variable: `arrow_only_movement`. Requests: driver follows illuminated arrow movement; driver takes a movement different from the illuminated arrow. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: a steady red with a green turn arrow faces the subject; the subject enters the intersection.

Timing to retain: the permission lasts only while the arrow is illuminated; entering for any movement other than the arrow's is the violation, at the moment the path departs from it.

Exceptions and numeric alternatives planned: the two-cycle exception for motorcycles, mopeds and cycles the text cites.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Native CPU construction: `native/build.py` authors eight unselected source-pinned requests across two controlled movements and four policies (primary, slower approach, elevated overview, two-second pre-approach dwell plus five-second yield hold). `native/prove_request.py` passes eight exact positives and 40 changed-source/signal/actor/blueprint negatives. `native/saved.py` processes 3,840 explicitly synthetic frame joins and `native/prove_saved.py` passes eight positives and 48 altered-source/frame/actor/signal negatives. `native/audit_request.py` independently checks all requested and synthetic saved rows plus four controlled movement pairs. `native/measurement-contract.json` identifies the original channels needed for each mandatory source observation. The steady red plus green arrow, other vehicle and yield interval are requested targets, not original observations. The three fallback switches have distinct requested changes. `native/prove_fallback_quality.py` measures authored speed and signal-to-entry timing and proves three synthetic trigger decisions (6 positives/8 negatives); an independent audit recomputes all eight measurements; original capture-quality triggers remain unmeasured.

Frozen offline compatibility: `native/build_offline.py` pins eight unselected constructions with `native/capture.py` as their entrypoint. All eight pass `runtime.py offline` with 56 CPU tests and no simulation. `native/audit_offline.py` checks 120 materialized file bytes and rejects a changed construction digest. The capture entrypoint's CPU `--check` path passes eight source-bound positives and eight altered-blueprint negatives. Original CARLA capture has not run. The code requires two distinct generated signal actors, physical ego and other vehicles, synchronized 480-frame actor/video streams, FFV1 media and world restoration; it does not claim the generated green actor visibly renders a directional arrow.

Original saved-processing CPU path: `native/process_original.py` validates exact source and generated map readback, two continuous physical actor identities and bodies, 480 synchronized actor/video rows, steady red plus green Native actor states, three decoded FFV1 streams in original mode, capture/restoration receipt and source-hashed review. It measures actual heading change, movement match and speed during the requested yield hold, leaving legal verdict null. Its explicitly synthetic source-shape fixtures pass eight positives and 72 altered actor/frame/body/lane/signal/media/review negatives; four controlled movement pairs retain a 90-degree versus zero-degree heading distinction. Marker media is refused in original mode. No original media or visual review has run.

Capture-bound fallback quality: `native/fallback_quality.py` now invokes the source-bound original processor before measuring physical approach speed, physical hold-to-entry time and source-hashed reviewed visibility frames. Its synthetic source-shape proof passes two positives and ten material negatives, including refusal to accept marker media as original. Original capture and human frame review have not run.

Blocker: Original CARLA signal, other-vehicle and driver behavior have not been captured. Native execution compatibility, directional-arrow pixels, original measured fallback triggers, original saved processing from actual media, legal yielding and cited two-cycle exception applicability remain unverified. The assignment stays blocked and unselected.

Resume: execute and measure the eight Native attempts, prove exact offline compatibility, source-bound saved processing and independent semantic audit, then review the cited provision and legal outcome before evaluating readiness.
