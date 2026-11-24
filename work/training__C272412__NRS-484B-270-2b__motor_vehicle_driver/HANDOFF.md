# NRS-484B-270-2b at C272412

## 2026-11-23 body-gap CPU continuation

The exact source sets a floor of 3 feet (0.9144 m) between **any portion**
of the motor vehicle and scooter during the pass, and separately requires
left-side passing and no return right until safely clear. The 3-foot floor
is a continuous minimum, not an average of gap samples. "Safely clear" and
due care remain judgment questions; the saved diagnostic below reports
longitudinal overlap and return ordering without inventing a legal margin.

`pass_cpu.py` constructs five 600-frame, 20 Hz, 30-second synthetic traces:
the two planned witness requests and the 2.9/3.0/3.1-foot probes. Its saved
reducer computes rectangle-body surface gaps at each abreast frame, checks
left-side motion and first right-return order, and binds frame, actor,
one-lane context and source hashes. Five positives and five altered-source
negatives pass. Negatives cover early return, missing frame, a second
same-direction lane, changed scooter identity and an unbound trace hash.
The 3-foot case measures 0.9144 m from authored geometry only; real body
extent and sensor uncertainty are still unmeasured.

Command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python
work/training__C272412__NRS-484B-270-2b__motor_vehicle_driver/pass_cpu.py
--prove` (exit 0; five positives, five negatives). Script SHA-256
`5bd81ca621573ef2ed9a4acb04b81f45d2c05b104c4536a6fb8977ae99ca4963`;
`pass-cpu-proof.json` SHA-256
`75869609687732ab9b3c6897871791265cc5d4d5ba329892b482e07e8067b737`.
No Native motion, four-camera pixels, real scooter identity, lane count,
legal safety judgment or verdict is claimed.

Next CPU work: build a real Native single-lane-per-direction pass with an
electric scooter, synchronize four original cameras, retain actual body
vertices and lane/marking context, bind all seven exact cases and the
cited-law centre/no-passing alternatives, add source-hashed measurement
contracts and fixtures, and run pinned offline, positive/negative
compatibility, saved-only, semantic and independent audit proofs. Status
remains `partial`.

Actor: `motor_vehicle_driver`. Frozen cell: `single_lane_per_direction` / `overtake_left` / `scooter_rider`.

Exact statutory source: NRS 484B.270(2)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Electric-scooter left passing and return-right ordering. Planned comparison variable: `cycle_pass_clearance`. Requests: driver passes scooter rider left with at least 3-foot observed gap; driver passes scooter rider left with less than 3-foot observed gap. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject overtakes a bicycle, electric bicycle or electric scooter going the same way; there is only one lane for traffic in that direction.

Timing to retain: the 3-foot clearance must hold for every instant of the abreast phase, not on average; no return to the right until safely clear of the rider.

Exceptions and numeric alternatives planned: crossing the centre of the highway or a no-passing zone is authorized for such a pass, if it is safe and the 3-foot clearance is kept, subject to the left-side and no-passing-zone rules the text cites; minimum bicycle/scooter pass gap numeric boundary 3 feet.

Unresolved judgment or rule composition: 'safe distance' beyond the stated 3 feet, and 'safely clear', are judgement elements; the 3 feet is the one concrete bound the text gives. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
