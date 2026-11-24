# C111343 / NRS 484A.450(3) CPU checkpoint

Status: partial. Neither planned case is selected. No original Native capture, legal safety judgment, physical success, or accepted recording is claimed. The frozen full-train membership has no rows for this assignment.

The exact law makes the stop conditional on safety. If a stop is required, a present nearest-side crosswalk is the first stopping reference; absent one, a clearly marked stop line is next; absent both, the nearest point with a view of intersecting-highway traffic applies. The current witness supports the present-crosswalk branch. The paired planned cases hold the sign, crosswalk, other traffic, weather, actor, and capture fixed while changing the first stop position.

`yield_crosswalk_scene.py` authors perpendicular roads, a governing YIELD sign, a present near-side crosswalk, intersecting traffic, two stop-position policies and four camera requests for 600 frames at 20 Hz. `measure_yield_crosswalk.py` requires original map/sign/crosswalk/body/motion/traffic/safety-context/camera source hashes, joins every Native frame to four camera frames, and measures first recorded rest of the front bumper relative to the near edge, crosswalk entry, and intersection entry. `yield-crosswalk-measurement-contract.json` distinguishes this geometry from the independent safety finding.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111343__NRS-484A-450-3__motor_vehicle_driver/prove_yield_crosswalk.py`. `yield-crosswalk-proof.json` records source-shaped synthetic before-crosswalk and within-crosswalk traces plus six negative checks. It is a CPU diagnostic, not an exact runtime offline/compatibility, saved-processing or acceptance proof.

Next CPU work: source the safety-stop condition, add the absent-crosswalk stop-line and nearest-viewpoint branches, bind selected exact cases to the pinned runtime with source acquisition, test offline/positive-negative compatibility and saved processing, and implement independent delivery and comparison audits. Keep partial until the assignment strict gate passes. CARLA and actual pixels remain local operator work.
