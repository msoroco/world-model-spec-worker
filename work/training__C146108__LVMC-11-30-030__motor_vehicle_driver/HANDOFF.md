# C146108 / LVMC 11.30.030 CPU checkpoint

Status: partial. The planned hold/pass cases remain unselected. No original Native event, legal verdict, physical completion or accepted recording is claimed. The frozen full-train membership is empty for this assignment.

The law covers a marked crosswalk and an unmarked crosswalk at an intersection. The lead vehicle must be stopped to permit a pedestrian to cross, and the ego must approach from the rear before overtaking and passing. The current witness supports a marked crossing. The paired request holds road, crosswalk, lead, pedestrian, ego actor, weather and capture fixed while varying the pass policy.

`crosswalk_pass_scene.py` authors a one-way two-lane road, marked crosswalk, stopped lead vehicle, crossing pedestrian, paired ego policies and four camera requests for 600 frames at 20 Hz. `measure_crosswalk_pass.py` requires original road/marking/lane/body/motion/camera hashes, joins all Native and camera frames, checks rear approach and lead rest, then measures adjacent longitudinal overlap and ego ahead while the pedestrian crosses. `crosswalk-pass-measurement-contract.json` records source requirements and limits.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C146108__LVMC-11-30-030__motor_vehicle_driver/prove_crosswalk_pass.py`. `crosswalk-pass-proof.json` has synthetic hold and pass traces plus seven negative source, actor and frame tests. It is a CPU diagnostic, not an exact runtime offline/compatibility, saved-processing or acceptance proof.

Next CPU work: add the unmarked intersection crosswalk branch, independently source the lead's stop purpose, bind selected exact cases to the pinned runtime and source acquisition, run offline and positive/negative compatibility and saved processing, then implement independent delivery and comparison audits. Keep partial until the scoped strict gate passes. CARLA and actual pixels remain local operator work.
