# training__C111277__NRS-484B-250-4__motor_vehicle_driver

Status: partial. This is a source-grounded planning return only, not a deployable delivery package.

Exact law: When a vehicle enters an intersection controlled by a traffic-control signal which is installed and has its vehicular signals uncovered, but is inoperative at the time the vehicle enters the intersection, the driver of the vehicle shall proceed as if a stop sign had been erected at each entrance to the intersection and shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After making such a stop, the driver shall proceed cautiously, yielding to vehicles which have previously completed a stop or are within the intersection.

## 2026-11-23 controller checkpoint

`native/controller.py` implements an observation-driven stop, hold and yield policy for the selected no-stop-line, near-crosswalk branch. It requires an installed uncovered inoperative signal governing the ego lane and a present crosswalk; it rejects changed stop-line hierarchy. The 20-frame hold and 0.05 m/s speed tolerance are engineering choices for observable source measurement, not legal cutoffs. A prior-stop approaching vehicle or one inside the intersection keeps the ego held. Native scene activation and source pixels remain unproven.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python native/prove_controller.py native/controller-proof.json` passed over 600 frames at 20 Hz. The controller entered hold at frame 150, yield at 169, and released at 241 after conflict clearance; a no-conflict trace released at 169. Operating signal, missing crosswalk and unexpected stop line were rejected. Controller SHA-256: `139b5fa43f73f43e65f2268fe16b518b80ad1a5843251215e678cd2e6af60990`; proof SHA-256: `7883579d7e64e503c92f0a3dccc118859f83f79a0d98c4fdedd0c33f65aa1f00`; log SHA-256: `6f4b701e0966917f8714caf0d0026b7f4a0718b55f7e0c2bfeac31de93ba3eca`. `runtime.py preflight` and assignment-scoped `worker_check.py --complete` exited 0. Status remains partial. Next CPU work: bind this policy to exact construction and capture, prove observed signal/geometry source binding, run current offline and compatibility, saved processing and candidate proofs, and independently review the two accepted recordings before proposing new captures.

Selected witness scope: No stop line; near-side crosswalk.. The case plan inventories 4 source topics and drafts one controlled comparison on `complete_halt_before_applicable_boundary`. Neither case has a Native realization or legal outcome.

The local snapshot lists 4 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining work: Native physical mechanism, four distinct candidate constructions, exact offline/compatibility recipes, measured saved fixtures and independent audit are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Use an installed uncovered but physically inoperative vehicular signal; verify stop-line, near crosswalk and nearest-view-point hierarchy, actual halt, cautious movement and priority.

Legal limit: The inoperative-signal branch cannot be replaced with an ordinary functioning red-light stop.
