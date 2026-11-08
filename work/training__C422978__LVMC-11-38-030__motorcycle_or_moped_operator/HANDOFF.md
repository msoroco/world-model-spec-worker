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

The proposed Native runner now has a CARLA motorcycle and four-camera capture path; CPU compilation passed, but no physical capture has run. The authored road is retained as `authored-road.xodr` in exact bundles so Native map readback can occupy `road.xodr`. The saved processor and finalizer pass eight synthetic exact-bundle positives and missing-source negatives, with independent audits and a strict measurement contract for disposition 0. All eight exact unselected bundles also pass synthetic full Core/Lean/render/final-decode compatibility and eight deleted-source negatives, with an independent audit. Remaining worker-owned work: original four-camera data and saved-body measurement; strict v2 selected recipe compatibility; city-sidewalk qualification and driveway rule composition; independent accepted comparison and selection. Physical feasibility and legal outcome remain unverified.

`prove-comparison.py` now binds all four exact candidate pairs to their saved source hashes, holds motorcycle identity, 4 m/s speed, longitudinal motion, map and frame mapping fixed, and measures roadway zero versus sidewalk positive occupancy. Four synthetic positives and eight changed-speed/frame-map negatives pass; `audit-comparison.py` independently recomputes all 480 raw rows per pair. This comparison is unselected and cannot establish city-sidewalk or legal status.

`native/measure_context.py` now checks an explicit source-hashed city/sidewalk/driveway geometry packet against the saved Native map readback and 480 motorcycle body rows. `native/prove_context.py` retains eight synthetic positive packets, six invalid map-hash, false-authority, and singular-transform packets, and two driveway controls. `native/audit_context.py` independently recomputes the rectangle intersections from raw body rows and verifies every retained packet hash. The roadway witness has zero moving sidewalk intersection frames; the sidewalk witness has 400, 415, 393, and 400 for primary through fallback3. This intersection metric includes a single boundary-touch frame in fallback2, whereas the earlier full-body occupancy metric counts 392. The synthetic city polygon is a geometry fixture only. City authority, driveway rule composition and legal verdict remain unreviewed.

The spatial processor is now in all eight exact constructions. Finalization requires `city-context.json`, records its source hash and geometry measurement beside occupancy, and retains the city, sidewalk and driveway polygons as recording context evidence. The measurement contract names the packet as an input. Eight exact offline runs, saved-package positives and negatives, finalization positives plus both observed-source and city-context removal negatives, and full Core/Lean/video positives and observed-source negatives pass. The corresponding independent audits pass. The four synthetic controlled comparisons and eight tamper negatives were rebound to these constructions and pass their independent audit. No original city packet, Native physical result, or legal determination has been produced.

The controlled comparison now also requires the exact same source-hashed city, sidewalk and driveway packet in both witnesses and checks that the finalization report retained its unreviewed legal status. Each of four candidate pairs passes. Sixteen speed, frame-map, city-boundary and driveway-polygon source-tamper negatives reject; their altered packets are retained under `native/comparison-negatives` and independently byte-audited. This remains a synthetic unselected comparison.

Resume: prove strict v2 selected recipe compatibility, then run the Native capture path and measure original motorcycle body overlap with the Native sidewalk lane before evaluating readiness.
