# C276263 original instrument service

`native/runner.py --capture` requires `--instrument-host` and `--instrument-port`.
The service must be connected to the original vehicle and responsible-person
observation system for this attempt. The worker does not provide that system or
assert that CARLA control requests, an empty rendered cabin, or zero speed prove
engine-off or unattended standing.

For each 20 Hz Native tick, the capture sends one JSON line with format
`c276263-instrument-request-v1`, `native_frame`, `actor_id`, vehicle heading,
and the separately read CARLA `front_left` and `front_right` wheel angles in degrees. The service
returns one JSON line with format `c276263-original-instrument-v1`, the same
frame and actor, `source_kind: original_instrumentation`, stable `instrument_id`,
`engine_method`, `wheel_calibration_id`, `attendance_method`, and
`responsible_person_id`. It must supply booleans `engine_running` and
`responsible_person_outside`, integer `occupant_count`, and a finite
`front_wheel_heading_to_curb_deg`. The wheel value needs a documented original
calibration to the measured right curb, not the requested steer setting.

`native/instrument_producer.py` supplies the source adapter interface. Its
engine, wheel, and attendance callbacks return independent same-frame readings
with actor and sensor identity. The producer retains these readings and their
hashes in every packet. It computes curb-relative front-wheel orientation from
two sensor headings, surveyed curb tangent, and bounded zero offsets, and
cross-checks the separate Native wheel API readbacks. The calibration embeds a
source-hashed curb survey with road ID, curb position, tangent, distance, map
hash, sensor ID, valid frame window, and angular uncertainty. Capture compares
that survey with the Native map readback. `audit_packet` recomputes derived
values from retained readings; `audit_stream` rejects missing frames, identity
changes, and calibration changes. Capture writes both per-frame source audits
and a whole-window audit. Diagnostic fake sources exercise these checks but
are rejected as original acquisition.
`serve_connection` accepts an already connected JSON-line stream and serves a
fixed 600-frame window. It rejects incomplete windows, frame gaps, and actor
changes. A local source adapter must connect the callbacks to physical readings
before this interface can be used for an original attempt.

Capture retains every response unmodified in `instrument-frames.jsonl`; saved
measurement hashes that original packet stream and cross-checks it against the
vehicle and attendance rows. The service must observe actual engine or motor operation, physical front-wheel
orientation, cabin occupancy, and the responsible person's location before,
during, and after leaving. Its identity and calibration record must be reviewed
with the original attempt. Capture rejects absent, stale, misjoined, nonfinite,
or command-derived packets. Saved measurement requires all 600 synchronized
frames, source hashes, and stable instrument/person identity. These CPU checks
do not establish physical accuracy or a statutory verdict.

The worker export includes the service interface and its CPU fake-source tests.
It contains no original sensor adapter, survey, source record, or reviewed
physical reading. A local operator must connect and review an engine-operation
sensor, calibrated wheel source, and attendance observation. If unavailable,
capture fails before claiming delivery; the case remains partial.

`native/delivery_audit.py` independently rechecks the 600 retained packets,
source hashes, actor join, and physical review receipt for each original attempt.
`native/comparison_delivery_audit.py` runs both per-attempt audits before
comparing fixed grade, curb, duration, attendance window and engine observation
against the separately reported brake and wheel differences. Both auditors
reject diagnostic packets as original evidence and return no legal verdict.
