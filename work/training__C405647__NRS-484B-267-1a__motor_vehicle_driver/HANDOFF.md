# NRS-484B-267-1a at C405647

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `emergency_vehicle`.

Exact statutory source: NRS 484B.267(1)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: authorized_emergency_vehicle_approach. Planned comparison variable: `emergency_vehicle_yield`. Requests: driver yields to immediately approaching flashing emergency vehicle; driver maintains conflicting course during immediate approach. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: an authorized emergency vehicle or regulatory-agency official vehicle is on immediate approach; it is using flashing lights of the required kind; the subject is the driver of another vehicle.

Timing to retain: the lamps and the approach precede the duty; the yield is owed from the moment the approach is immediate; the duty holds throughout the approach.

Exceptions and numeric alternatives planned: when otherwise directed by a law enforcement officer.

Unresolved judgment or rule composition: 'immediate approach' bounds the distance or time at which the duty starts and must be declared; whether the lamps meet the statutory specification is an equipment fact; the observable is a flashing red or blue lamp. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Construction now begun: `native/geometry.py` authors a 260 m two-lane OpenDRIVE road and 480-frame paired subject/emergency approach requests. Both cases share the same initial state, emergency approach and flashing-lamp timing request; `witness_1` requests clearing the inner lane, while `witness_2` requests maintaining that lane. Its CPU geometry check passes. `native/source-scope.json` records the incorporated equipment and authority facts from the official Nevada sources. `native/measure_saved.py` measures source-bound saved relative motion, full-body inner-lane clearance, approach catch-up and lamp-state transitions, without legal inference. The CPU synthetic proof passes both controlled cases and rejects changed law hash, missing lamp sequence and changed frame time. Retained packets in `synthetic-local/` have separate analysis reports, and `audit-synthetic-saved.py` independently recomputes the common approach, lamp transitions, clearance and catch-up. `witness_1` clears the inner lane at frame 81 before longitudinal catch-up at frame 182; `witness_2` never clears it. These are authored/synthetic requests, not Native capture, original pixels, evidence that the lamp is compliant, a determination that approach is legally immediate, or a legal outcome.

Eight unselected construction policies now cover both witnesses, each with primary plus three distinct fallbacks. `fallback1` changes clearance timing and overview placement, triggered by saved full-body clearance or unwanted lane drift. `fallback2` moves the approaching actor's starting position, triggered when measured catch-up falls outside the 24 s capture window. `fallback3` changes subject speed and lamp camera field of view, triggered by a source-hashed front-lamp visibility packet below a 75% framing target. These thresholds are capture engineering criteria, not statutory definitions. Six synthetic positive/non-trigger pairs pass, including a wrong pixel-source-hash rejection. The independent candidate audit checks eight source/map-bound plans, fixed pair conditions and distinct policies. Retained synthetic rows now pass the case-specific measurement contracts, missing-source and changed-source negatives, and independent saved audit. None of these source packets prove actual original pixels, Native tracking, vehicle authority, lamp compliance or legal immediacy.

Blocker: Native actor/camera capture, exact pinned offline and portable compatibility, independent selected delivery audit, statutory branch closure and queue construction remain unfinished worker-owned work. Physical feasibility and legal outcome remain unverified.

The candidate manifest stores both authored OpenDRIVE tracks and y-reflected proposed Native tracks for all eight policies. The independent audit checks the reflection and 480 source rows for each. This is a coordinate request check, not CARLA lane readback.

Resume: build the executable Native actor/camera capture and lane readback; bind statutory authority and lamp evidence; materialize exact offline bundles, positive/negative portable compatibility, selected saved/Core/Lean/video proofs and independent delivery audit; close statutory branches only when their CPU proofs pass; then order the GPU queue.
