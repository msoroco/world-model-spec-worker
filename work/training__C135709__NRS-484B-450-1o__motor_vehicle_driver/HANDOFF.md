# C135709 / NRS 484B.450(1)(o) CPU checkpoint

Status: partial. The planned parking cases remain unselected. No original Native event, legal verdict, accepted recording, or physical device verification is claimed. The frozen full-train membership is empty for this assignment.

The law covers stopping, standing and parking wherever an official device prohibits the action, subject to traffic-conflict necessity, law compliance, police direction, or official-device direction. The current witness concerns parking on a narrow road within a governed zone. The planned pair varies only parked vehicle overlap with the zone while holding the device, action, exceptions, actor, weather and capture fixed.

`prohibited_parking_scene.py` authors the narrow road, official NO_PARKING sign, governed longitudinal zone, paired park points and four camera requests for 600 frames at 20 Hz. `measure_prohibited_parking.py` requires original map/device/zone/condition/civil-time/body/motion/exception/camera hashes, joins every Native frame and camera, and measures parked body overlap with the governed zone. `prohibited-parking-measurement-contract.json` records source and legal limits.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C135709__NRS-484B-450-1o__motor_vehicle_driver/prove_prohibited_parking.py`. `prohibited-parking-proof.json` contains synthetic source-shaped outside- and inside-zone fixtures and seven negative tests. This is only a CPU diagnostic, not an exact runtime offline/compatibility, saved-processing or acceptance proof.

Next CPU work: source the official device and active conditions; enumerate stop/stand modes and all four exception branches; bind selected exact cases to the pinned runtime with source acquisition; run offline and positive/negative compatibility, saved processing, and independent delivery/comparison audits. Keep partial until the assignment strict gate passes. CARLA and original pixels remain local operator work.
