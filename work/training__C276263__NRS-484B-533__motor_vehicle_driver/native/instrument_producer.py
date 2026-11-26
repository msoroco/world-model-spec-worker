"""Source-bound producer and independent audit for three original observations.

Callbacks must read original sensors. CPU fakes exercise the interface only;
they cannot establish that a physical sensor or calibration exists.
"""
import hashlib
import json
import math


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def signed(value):
    return (value + 180) % 360 - 180


def calibration_preflight(record, frame):
    """Require a surveyed curb and bounded wheel-sensor calibration."""
    if not isinstance(record, dict) or record.get('format') != 'c276263-curb-calibration-v1':
        raise ValueError('Original curb calibration record missing')
    for key in ('calibration_id', 'survey_method', 'sensor_method',
                'wheel_sensor_id', 'curb_survey_id'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError('Curb calibration method or identity missing: ' + key)
    if record.get('source_kind') != 'original_survey' or record.get('curb_side') != 'right':
        raise ValueError('Measured right-curb survey missing')
    if (not finite(record.get('curb_tangent_heading_world_deg')) or
            not finite(record.get('curb_distance_m')) or
            not 0 < record['curb_distance_m'] < 10):
        raise ValueError('Original curb geometry missing')
    offsets = record.get('wheel_zero_offsets_deg')
    if (not isinstance(offsets, dict) or set(offsets) != {'front_left', 'front_right'} or
            any(not finite(v) or abs(v) > 10 for v in offsets.values())):
        raise ValueError('Wheel zero calibration missing')
    uncertainty = record.get('max_angular_error_deg')
    if not finite(uncertainty) or not 0 < uncertainty <= 5:
        raise ValueError('Wheel angular uncertainty unbounded')
    window = record.get('valid_native_frames')
    if (not isinstance(window, list) or len(window) != 2 or
            any(type(x) is not int for x in window) or
            window[0] > frame or window[1] < frame):
        raise ValueError('Wheel calibration invalid for Native frame')
    survey = record.get('curb_survey')
    if (not isinstance(survey, dict) or
            survey.get('source_kind') != 'original_survey' or
            survey.get('survey_id') != record['curb_survey_id'] or
            survey.get('road_id') != 1 or
            not finite(survey.get('right_curb_y_m')) or
            not finite(survey.get('curb_tangent_heading_world_deg')) or
            not finite(survey.get('curb_distance_m')) or
            not isinstance(survey.get('road_xodr_sha256'), str) or
            len(survey['road_xodr_sha256']) != 64 or
            survey['road_xodr_sha256'] == '0' * 64):
        raise ValueError('Original curb survey geometry source missing')
    proof = record.get('curb_survey_sha256')
    if proof != digest(survey):
        raise ValueError('Original curb survey hash differs')
    if (abs(signed(survey['curb_tangent_heading_world_deg'] -
                   record['curb_tangent_heading_world_deg'])) > 1e-6 or
            abs(survey['curb_distance_m'] - record['curb_distance_m']) > 1e-6):
        raise ValueError('Curb survey and calibration geometry differ')
    return record


def _source(reading, kind, frame, actor_id):
    if (not isinstance(reading, dict) or reading.get('source_kind') != 'original_sensor' or
            reading.get('native_frame') != frame or reading.get('actor_id') != actor_id or
            not isinstance(reading.get('sensor_id'), str) or not reading['sensor_id'] or
            not isinstance(reading.get('method'), str) or not reading['method']):
        raise ValueError('Original ' + kind + ' sensor identity/frame missing')
    if reading['method'] in ('command', 'requested_control', 'speed_proxy',
                             'empty_render', 'case_label'):
        raise ValueError('Proxy is not original ' + kind + ' observation')
    return reading


def build_packet(frame, actor_id, native_wheels, actor_heading, calibration,
                 engine, wheels, attendance, diagnostic=False):
    """Join independent source readings; never derive engine/attendance from controls."""
    if type(frame) is not int or type(actor_id) is not int or not finite(actor_heading):
        raise ValueError('Original Native frame, actor, or heading missing')
    calibration_preflight(calibration, frame)
    if not isinstance(native_wheels, dict) or set(native_wheels) != {'front_left', 'front_right'}:
        raise ValueError('Original Native wheel readbacks missing')
    if any(not finite(x) for x in native_wheels.values()):
        raise ValueError('Nonfinite Native wheel readback')
    engine = _source(engine, 'engine', frame, actor_id)
    wheels = _source(wheels, 'wheel', frame, actor_id)
    attendance = _source(attendance, 'attendance', frame, actor_id)
    if type(engine.get('engine_running')) is not bool:
        raise ValueError('Original engine operation state missing')
    if wheels['sensor_id'] != calibration['wheel_sensor_id']:
        raise ValueError('Calibrated wheel sensor identity differs')
    headings = wheels.get('front_wheel_heading_world_deg')
    if (not isinstance(headings, dict) or set(headings) != set(native_wheels) or
            any(not finite(x) for x in headings.values())):
        raise ValueError('Actual front-wheel heading source missing')
    relative = {}
    for key in native_wheels:
        corrected = signed(headings[key] - calibration['wheel_zero_offsets_deg'][key]
                           - actor_heading)
        if abs(signed(corrected - native_wheels[key])) > calibration['max_angular_error_deg']:
            raise ValueError('Wheel source and Native readback disagree')
        relative[key] = signed(headings[key] - calibration['wheel_zero_offsets_deg'][key]
                               - calibration['curb_tangent_heading_world_deg'])
    if abs(signed(relative['front_left'] - relative['front_right'])) > 25:
        raise ValueError('Front-wheel source pair disagrees')
    if (type(attendance.get('occupant_count')) is not int or
            attendance['occupant_count'] < 0 or
            type(attendance.get('responsible_person_outside')) is not bool or
            not isinstance(attendance.get('responsible_person_id'), str) or
            not attendance['responsible_person_id']):
        raise ValueError('Identified original attendance state missing')
    if attendance['responsible_person_outside'] and attendance['occupant_count'] > 0:
        raise ValueError('Attendance source conflicts with occupied cabin')
    source = {'engine': engine, 'wheels': wheels, 'attendance': attendance}
    return {'format': 'c276263-original-instrument-v1',
            'native_frame': frame, 'actor_id': actor_id,
            'source_kind': 'original_instrumentation',
            'diagnostic_fixture': bool(diagnostic),
            'instrument_id': 'c276263-source-join-v1',
            'engine_method': engine['method'],
            'engine_running': engine['engine_running'],
            'wheel_calibration_id': calibration['calibration_id'],
            'front_wheel_heading_to_curb_deg':
                sum(relative.values()) / 2,
            'attendance_method': attendance['method'],
            'responsible_person_id': attendance['responsible_person_id'],
            'occupant_count': attendance['occupant_count'],
            'responsible_person_outside': attendance['responsible_person_outside'],
            'calibration': calibration,
            'native_front_wheel_angles_deg': native_wheels,
            'actor_heading_world_deg': actor_heading,
            'source_observations': source,
            'source_sha256': {name: digest(value) for name, value in source.items()}}


def audit_packet(packet, allow_diagnostic=False):
    """Recompute wheel geometry and source hashes from retained readings."""
    if not isinstance(packet, dict) or packet.get('format') != 'c276263-original-instrument-v1':
        raise ValueError('Original packet format missing')
    if (packet.get('source_kind') != 'original_instrumentation' or
            packet.get('instrument_id') != 'c276263-source-join-v1' or
            type(packet.get('diagnostic_fixture')) is not bool):
        raise ValueError('Original packet provenance differs')
    if packet.get('diagnostic_fixture') and not allow_diagnostic:
        raise ValueError('Diagnostic sensor packet cannot be original acquisition')
    frame, actor = packet.get('native_frame'), packet.get('actor_id')
    source = packet.get('source_observations')
    if not isinstance(source, dict) or set(source) != {'engine', 'wheels', 'attendance'}:
        raise ValueError('Retained original source readings missing')
    if packet.get('source_sha256') != {name: digest(value) for name, value in source.items()}:
        raise ValueError('Original source reading hash differs')
    rebuilt = build_packet(frame, actor, packet.get('native_front_wheel_angles_deg'),
        packet.get('actor_heading_world_deg'), packet.get('calibration'),
        source['engine'], source['wheels'], source['attendance'],
        diagnostic=bool(packet.get('diagnostic_fixture')))
    for key in ('engine_running', 'front_wheel_heading_to_curb_deg',
                'occupant_count', 'responsible_person_outside',
                'responsible_person_id', 'wheel_calibration_id',
                'engine_method', 'attendance_method', 'source_kind',
                'instrument_id', 'diagnostic_fixture'):
        if packet.get(key) != rebuilt[key]:
            raise ValueError('Derived packet differs from retained source: ' + key)
    return {'source_hashes': rebuilt['source_sha256'],
            'calibration_sha256': digest(rebuilt['calibration']),
            'frame': frame, 'actor_id': actor,
            'diagnostic_fixture': bool(packet.get('diagnostic_fixture')),
            'physical_review_required': True}


def audit_stream(packets, expected_frames=600, allow_diagnostic=False):
    """Reject incomplete, mixed-identity, or mixed-calibration attempts."""
    if len(packets) != expected_frames or expected_frames <= 0:
        raise ValueError('Complete source-observed instrument window required')
    first = packets[0]
    identities = None
    prior = None
    for packet in packets:
        audit_packet(packet, allow_diagnostic=allow_diagnostic)
        frame = packet['native_frame']
        if prior is not None and frame != prior + 1:
            raise ValueError('Instrument source Native frame gap')
        prior = frame
        source = packet['source_observations']
        current = (packet['actor_id'], packet['instrument_id'],
            packet['wheel_calibration_id'], digest(packet['calibration']),
            packet['responsible_person_id'],
            tuple(source[name]['sensor_id'] for name in ('engine', 'wheels', 'attendance')))
        if identities is None:
            identities = current
        elif current != identities:
            raise ValueError('Instrument source identity or calibration changed')
    return {'format': 'c276263-independent-source-audit-v1',
            'passed': True, 'frames': len(packets),
            'first_native_frame': first['native_frame'],
            'last_native_frame': prior,
            'actor_id': identities[0],
            'calibration_sha256': identities[3],
            'source_sensor_ids': list(identities[-1]),
            'diagnostic_fixture': bool(first.get('diagnostic_fixture')),
            'physical_calibration_reviewed': False,
            'legal_acceptance_claimed': False}


class SourceProducer:
    """Callbacks are physical source adapters, not CARLA commands or labels."""

    def __init__(self, engine, wheels, attendance, calibration):
        self.engine = engine
        self.wheels = wheels
        self.attendance = attendance
        self.calibration = calibration

    def sample(self, frame, actor_id, native_wheels, actor_heading, diagnostic=False):
        return build_packet(frame, actor_id, native_wheels, actor_heading,
            self.calibration, self.engine(frame, actor_id),
            self.wheels(frame, actor_id), self.attendance(frame, actor_id),
            diagnostic=diagnostic)


def serve_connection(reader, writer, producer, frames=600, diagnostic=False):
    """Serve the capture JSON-line protocol on an already accepted connection."""
    if type(frames) is not int or frames <= 0:
        raise ValueError('Positive fixed source window required')
    actor_id = None
    prior_frame = None
    packets = []
    for _ in range(frames):
        line = reader.readline()
        if not line:
            raise ValueError('Source service request window incomplete')
        request = json.loads(line)
        if request.get('format') != 'c276263-instrument-request-v1':
            raise ValueError('Source service request format differs')
        frame, actor = request.get('native_frame'), request.get('actor_id')
        if (type(frame) is not int or type(actor) is not int or
                (actor_id is not None and actor != actor_id) or
                (prior_frame is not None and frame != prior_frame + 1)):
            raise ValueError('Source service frame or actor continuity differs')
        actor_id, prior_frame = actor, frame
        packet = producer.sample(frame, actor,
            request.get('native_front_wheel_angles_deg'),
            request.get('actor_heading_world_deg'), diagnostic=diagnostic)
        audit_packet(packet, allow_diagnostic=diagnostic)
        writer.write(json.dumps(packet, sort_keys=True) + '\n')
        writer.flush()
        packets.append(packet)
    return audit_stream(packets, expected_frames=frames,
                        allow_diagnostic=diagnostic)
