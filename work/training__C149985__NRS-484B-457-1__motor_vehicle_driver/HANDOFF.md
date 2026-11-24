# C149985 / NRS 484B.457(1) CPU checkpoint

Status: partial. The three right-curb boundary cases remain unselected. No original Native motion, accepted recording, physical success or legal verdict is claimed. The frozen full-train membership has no rows for this assignment.

The default rule concerns stopped or parked vehicles on a highway with adjacent curbs: right-hand wheels parallel to and within 18 inches of the right-hand curb. Subsections (2) and (3) allow local ordinances for left-curb parking on a one-way highway and angle parking, with a separate DOT-maintained-highway determination condition for angle parking. The current witness is the default right-curb branch. The planned comparison varies requested clearance at 16, 18 and 20 inches while holding the road, curb, vehicle, heading, parking action, weather and capture fixed.

`right_curb_scene.py` authors a one-way road with both curbs, three right-wheel target positions, parking-brake policy and four cameras for 600 frames at 20 Hz. `measure_right_curb.py` requires original map/curb/wheel/body/motion/parking/ordinance/camera hashes, joins every Native and camera frame, and measures both right-wheel outer-edge gaps and heading difference over the parked interval. `right-curb-measurement-contract.json` records the 18-inch statutory boundary and need for source uncertainty review.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C149985__NRS-484B-457-1__motor_vehicle_driver/prove_right_curb.py`. `right-curb-proof.json` contains synthetic source-shaped 16/18/20-inch fixtures and seven negative tests. It is a CPU diagnostic, not an exact runtime offline/compatibility, saved-processing or legal acceptance proof.

Next CPU work: source the local ordinance alternatives and DOT determination, add stopped-vehicle and exception comparisons, bind selected exact cases to the pinned runtime and source acquisition, run offline and positive/negative compatibility and saved processing, and implement independent delivery/comparison audits. Keep partial until the scoped strict gate passes. CARLA and original pixels remain local operator work.
