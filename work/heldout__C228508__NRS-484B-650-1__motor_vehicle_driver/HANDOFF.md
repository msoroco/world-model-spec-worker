# heldout__C228508__NRS-484B-650-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-650-1, cell: C228508, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C228508__NRS-484B-650-1__motor_vehicle_driver/assignment.json` (72d8f43f7472b7f990199e734638d9e45dfe3f282f9af81b033016c422abc720).

Exact law text: A driver commits an offense of aggressive driving if, during any single, continuous period of driving within the course of 1 mile, the driver does all the following, in any sequence: (a) Commits one or more acts of speeding in violation of NRS 484B.363 or 484B.600 [NRS-484B-363-1, NRS-484B-363-2, NRS-484B-600-1a, NRS-484B-600-1b, NRS-484B-600-1c, NRS-484B-600-1e]. (b) Commits two or more of the following acts, in any combination, or commits any of the following acts more than once: (1) Failing to obey an official traffic-control device in violation of NRS 484B.300 [NRS-484B-300-1]. (2) Overtaking and passing another vehicle upon the right by driving off the paved portion of the highway in violation of NRS 484B.210 [NRS-484B-210-3]. (3) Improper or unsafe driving upon a highway that has marked lanes for traffic in violation of NRS 484B.223 [NRS-484B-223-1b, NRS-484B-223-2, NRS-484B-223-3a, NRS-484B-223-3b, NRS-484B-223-3c, NRS-484B-223-4a, NRS-484B-223-4b]. (4) Following another vehicle too closely in violation of NRS 484B.127 [LVMC-11-12-080-A, NRS-484B-127-2, NRS-484B-127-3]. (5) Failing to yield the right-of-way in violation of any provision of NRS 484B.250 to 484B.267, inclusive [NRS-484B-250-1, NRS-484B-250-2, NRS-484B-250-3, NRS-484B-250-4, NRS-484B-253, NRS-484B-257-1, NRS-484B-257-2, NRS-484B-260, NRS-484B-263, NRS-484B-267-1a, NRS-484B-267-1b, NRS-484B-267-1c, NRS-484B-267-2a, NRS-484B-267-2b, NRS-484B-267-2c, NRS-484B-267-2d, NRS-484B-267-2e, NRS-484B-267-2f]. (c) Creates an immediate hazard, regardless of its duration, to another vehicle or to another person, whether or not the other person is riding in or upon the vehicle of the driver or any other vehicle.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C228508__NRS-484B-650-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C228508__NRS-484B-650-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- single continuous driving period within one mile, with measured path/time window
- one or more speeding acts under listed governing provisions
- two different listed predicate acts versus one repeated listed act
- each listed predicate category: device, off-pavement right pass, marked-lane driving, too-close following, failure to yield
- immediate hazard to person or vehicle, independent of hazard duration
- missing-element comparisons holding all other predicates fixed

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.
