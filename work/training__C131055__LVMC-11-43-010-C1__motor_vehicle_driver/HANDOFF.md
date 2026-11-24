# C131055 / LVMC 11.43.010(C)(1) CPU checkpoint

Status: partial. The left-turn lane-choice cases remain unselected; no original Native motion, legal conclusion, or accepted-recording reuse is claimed.

The law requires the left lane for a left turn or a U-turn within a roundabout. This cell is a multilane roundabout with an exit-roundabout maneuver and lane allocation. Five full-train membership rows exist but have no source-hashed equivalence review. The planned pair compares inner left and outer right circulatory lanes for the same left-turn exit intention. U-turn intention needs its own linked comparison or source-backed coverage disposition.

`roundabout_scene.py` authors an inner and outer circulatory lane, south entry, west exit, matched 270-degree waypoint paths, lane policy, and four camera requests for 600 frames at 20 Hz. `measure_roundabout_lane.py` requires original map/lane/link/body/motion/intention/camera source hashes, joins all Native frames and cameras, verifies entry/circulation/exit order, classifies ring lane occupancy by sourced lane radii, and measures lane changes, angular sweep and exit heading. `roundabout-lane-measurement-contract.json` records source requirements and legal limits.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C131055__LVMC-11-43-010-C1__motor_vehicle_driver/prove_roundabout_lane.py`. The generated `roundabout-lane-proof.json` has synthetic source-shaped left/right fixtures and seven negative tests. It proves only the CPU diagnostic code, not an exact runtime construction, physical lane use, saved processing, or legal outcome.

Next CPU work: inspect accepted recording source packets and write source-backed reuse or gaps; add U-turn comparison if not covered; bind actual catalog geometry and controller to the pinned runtime; run exact offline, positive/negative compatibility, saved processing and independent delivery/comparison audits for selected cases and risk-based fallbacks. Keep partial until the scoped strict gate passes. CARLA execution and original-pixel review remain local operator work.
