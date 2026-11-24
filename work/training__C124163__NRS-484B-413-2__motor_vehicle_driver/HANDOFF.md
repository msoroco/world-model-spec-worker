# training__C124163__NRS-484B-413-2__motor_vehicle_driver

Status: partial. Source-grounded planning and synthetic measurements are checkpoints, not a deployable delivery package.

Exact law: A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.

Selected witness scope: NRS-484B-413-2. Explicitly record completed equivalence and pending limitations. The case plan inventories 4 source topics and drafts one controlled comparison on `continuous_signal_distance_before_course_change`. Neither case has a Native realization or legal outcome.

The local snapshot lists 3 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining work: Native physical mechanism, exact primary and risk-assessed fallback constructions, current offline/compatibility recipes, measured saved fixtures and independent delivery audit are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, exact primary and risk-based fallback plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Measure continuous physical indicator/hand-signal activity along actual traveled distance before course-change onset; distinguish 100-foot business/residential from 300-foot other-area branch.

Legal limit: Weather cannot waive the distance rule; command station is not observed onset or visible flashing.

## 2026-11-23 continuous-distance source checkpoint

`native/signal_distance.py` measures a contiguous run of source-labeled signal activity backward from one course-change onset, using retained Native odometer samples rather than command timing. Four 30-second/20-Hz synthetic traces exercise both statutory distance forks: other-area clear-weather 100 m versus 70 m (300 ft = 91.44 m), and business/residential rainy-weather 35.2 m versus 20 m (100 ft = 30.48 m). Weather is fixed within each comparison; no weather waiver is applied. These are numeric software diagnostics, not observed indicator pixels or legal findings. The origin of actual district class, weather, turn onset and visible continuous signal remains to be established by Native source capture.

`native/prove_signal_sources.py` passed four positives and rejected missing rows, altered signal row and changed district context by source hash. `native/audit_signal_comparison.py` independently checked exact 600-frame kinematics, context equality within each pair and signal activity as the only varied row field. Meter SHA-256 `7880c289bc1b11d4a0bd6716d3d405edf62c0ef87af4c30b30072e54c01563af`; source proof SHA-256 `d95f4de77d4705b85f30e5d26daa44eed851db065ef172e92f5338863da941ea`; comparison audit SHA-256 `73344b23e780eb9b2b986273a5fe4514946bcf20856aa5326190ce3b55797310`. Pinned preflight passed. Status remains partial. Next CPU work: implement Native turn/indicator and four-camera capture, bind selected exact cases to current offline/compatibility and recorded-only saved processing, and inspect accepted evidence before proposing new captures.


## 2026-11-23 Native turn setup CPU checkpoint

`native/turn_capture_plan.py` provides a proposed same-cell left-turn actor and four source-camera setup for other-area clear-weather and district rainy-weather pairs, 600 frames at 20 Hz. It requires a Native median opening, lane, route, district and weather survey before spawning. `native/prove_turn_setup.py` bound each request distance to its retained source measurement (100, 70, 35.2 and 20 m), checked comparison isolation, rejected a missing survey and destroyed all owned actors after a simulated partial camera-spawn failure. Setup SHA-256 `f3adee54e87be31d129aa102806ae2fc814c9cbb50a75926ee1b66009a0e4e4d`; proof SHA-256 `4d9ca6eb9e16b0a2f2d4580b4e435473bb2266b01528e58e85a55622a9ff856b`. This is a CPU mock setup, not Native signal visibility, actual traveled distance or a legal finding. Status stays partial.
