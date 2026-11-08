# LVMC-11-38-030 at C422978

Actor: `motorcycle_or_moped_operator`. Frozen cell: `two_lane_two_way` / `travel` / `sidewalk`.

Exact statutory source: LVMC 11.38.030. Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Motorcycle riding upon a sidewalk. Planned comparison variable: `sidewalk_motorcycle_occupancy`. Requests: rider travels on roadway without entering sidewalk; rider rides motorcycle on city sidewalk. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject rides a motorcycle or motor scooter upon a sidewalk of the City.

Timing to retain: judged at every instant the machine is ridden on the sidewalk.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: the state rule permits crossing a sidewalk at a driveway; a reading must say how the municipal ban and that permission compose. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

CPU construction progress: `native/build.py` authors a two-way road with an explicit right sidewalk lane and eight source-bound 480-frame motorcycle requests. `native/prove_triggers.py` retains synthetic saved-body trigger and non-trigger packets for three distinct fallbacks in both cases, plus changed-camera-hash and changed-body negatives. `native/audit_construction.py` independently recomputes road lane types, all eight request metrics and all 12 trigger fixtures. `build_offline.py` materializes the eight exact unselected bundles; `run-draft-offline.py` passes the pinned offline command and three unit tests for each; `audit-draft-offline.py` independently checks source bytes, construction hashes and receipt logs. These are CPU construction requests and synthetic diagnostics, not original Native observations.

The proposed Native runner now has a CARLA motorcycle and four-camera capture path; CPU compilation passed, but no physical capture has run. The saved processor and finalizer pass eight synthetic exact-bundle positives and missing-source negatives, with independent audits and a strict measurement contract for disposition 0. Remaining worker-owned work: original four-camera data and saved-body measurement; positive/negative full Core/Lean/video package compatibility; city-sidewalk qualification and driveway rule composition; independent accepted comparison and selection. Physical feasibility and legal outcome remain unverified.

Resume: prove positive/negative Core/Lean/video compatibility for all eight exact bundles, then run the Native capture path and measure original motorcycle body overlap with the Native sidewalk lane before evaluating readiness.
