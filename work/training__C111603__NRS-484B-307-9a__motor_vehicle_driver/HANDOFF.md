# NRS-484B-307-9a at C111603

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `turn` / `other_vehicle`.

Exact statutory source: NRS 484B.307(9)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Turn with other intersection traffic. Planned comparison variable: `arrow_only_movement`. Requests: driver follows illuminated arrow movement; driver takes a movement different from the illuminated arrow. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: a steady red with a green turn arrow faces the subject; the subject enters the intersection.

Timing to retain: the permission lasts only while the arrow is illuminated; entering for any movement other than the arrow's is the violation, at the moment the path departs from it.

Exceptions and numeric alternatives planned: the two-cycle exception for motorcycles, mopeds and cycles the text cites.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Native CPU construction: `native/build.py` authors eight unselected source-pinned requests across two controlled movements and four policies (primary, slower approach, elevated overview, two-second dwell). `native/prove_request.py` passes eight exact positives and 32 changed-source/signal/actor negatives. `native/saved.py` processes 3,840 explicitly synthetic frame joins and `native/prove_saved.py` passes eight positives and 48 altered-source/frame/actor/signal negatives. `native/audit_request.py` independently checks all requested and synthetic saved rows plus four controlled movement pairs. `native/measurement-contract.json` identifies the original channels needed for each mandatory source observation. The steady red plus green arrow, other vehicle and yield interval are requested targets, not original observations. The three fallback switches have distinct requested changes; their capture-quality trigger thresholds remain unmeasured.

Blocker: Original CARLA signal, other-vehicle and driver behavior have not been captured. Native runtime compatibility, measured fallback triggers, original saved processing, legal yielding and cited two-cycle exception applicability remain unverified. The assignment stays blocked and unselected.

Resume: execute and measure the eight Native attempts, prove exact offline compatibility, source-bound saved processing and independent semantic audit, then review the cited provision and legal outcome before evaluating readiness.
