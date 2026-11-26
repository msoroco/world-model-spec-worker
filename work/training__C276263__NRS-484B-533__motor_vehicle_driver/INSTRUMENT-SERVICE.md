# C276263 original instrument service

`native/runner.py --capture` requires `--instrument-host` and `--instrument-port`.
The service must be connected to the original vehicle and responsible-person
observation system for this attempt. The worker does not provide that system or
assert that CARLA control requests, an empty rendered cabin, or zero speed prove
engine-off or unattended standing.

For each 20 Hz Native tick, the capture sends one JSON line with format
`c276263-instrument-request-v1`, `native_frame`, `actor_id`, and the separately
read CARLA `front_left` and `front_right` wheel angles in degrees. The service
returns one JSON line with format `c276263-original-instrument-v1`, the same
frame and actor, `source_kind: original_instrumentation`, stable `instrument_id`,
`engine_method`, `wheel_calibration_id`, `attendance_method`, and
`responsible_person_id`. It must supply booleans `engine_running` and
`responsible_person_outside`, integer `occupant_count`, and a finite
`front_wheel_heading_to_curb_deg`. The wheel value needs a documented original
calibration to the measured right curb, not the requested steer setting.

Capture retains every response unmodified in `instrument-frames.jsonl`; saved
measurement hashes that original packet stream and cross-checks it against the
vehicle and attendance rows. The service must observe actual engine or motor operation, physical front-wheel
orientation, cabin occupancy, and the responsible person's location before,
during, and after leaving. Its identity and calibration record must be reviewed
with the original attempt. Capture rejects absent, stale, misjoined, nonfinite,
or command-derived packets. Saved measurement requires all 600 synchronized
frames, source hashes, and stable instrument/person identity. These CPU checks
do not establish physical accuracy or a statutory verdict.

No original service implementation or source record is present in this worker
export. The local prerequisite is a reviewed, frame-synchronous instrument
producer with an engine-operation sensor, calibrated wheel source, and
attendance observation. If it is unavailable, capture fails before claiming
delivery; the case remains partial.
