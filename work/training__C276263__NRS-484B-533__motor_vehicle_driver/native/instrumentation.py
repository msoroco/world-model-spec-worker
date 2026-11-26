"""Frame-synchronous original-instrument boundary for the graded-stand scene.

The local operator must provide a real vehicle/attendance instrument service.
This module never infers engine operation or occupancy from CARLA commands.
"""
import json
import math
import socket


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def wheel_angles(vehicle, carla):
    """Preserve both original CARLA front-wheel observations separately."""
    attributes = dict(getattr(vehicle, 'attributes', {}))
    if str(attributes.get('number_of_wheels')) != '4':
        raise ValueError('Four-wheel motor-vehicle blueprint readback required')
    result = {}
    for key, name in (('front_left', 'FL_Wheel'), ('front_right', 'FR_Wheel')):
        value = vehicle.get_wheel_steer_angle(getattr(carla.VehicleWheelLocation, name))
        if not _number(value):
            raise ValueError('Original front-wheel angle missing: ' + key)
        result[key] = float(value)
    return result


def validate_packet(packet, frame, actor_id):
    """Reject stale, mislabeled, and command-derived instrument responses."""
    if not isinstance(packet, dict) or packet.get('format') != 'c276263-original-instrument-v1':
        raise ValueError('Original instrument packet format missing')
    if packet.get('native_frame') != frame or packet.get('actor_id') != actor_id:
        raise ValueError('Original instrument frame or actor join differs')
    if packet.get('source_kind') != 'original_instrumentation':
        raise ValueError('Original instrument provenance missing')
    for name in ('instrument_id', 'engine_method', 'wheel_calibration_id',
                 'attendance_method', 'responsible_person_id'):
        if not isinstance(packet.get(name), str) or not packet[name].strip():
            raise ValueError('Original instrument identity or method missing: ' + name)
    if packet['engine_method'] in ('command', 'requested_control', 'speed_proxy'):
        raise ValueError('Engine command or speed is not original operation state')
    if packet['attendance_method'] in ('case_label', 'empty_render', 'requested_control'):
        raise ValueError('Attendance label is not original occupancy state')
    if (type(packet.get('engine_running')) is not bool or
            type(packet.get('occupant_count')) is not int or packet['occupant_count'] < 0 or
            type(packet.get('responsible_person_outside')) is not bool or
            not _number(packet.get('front_wheel_heading_to_curb_deg'))):
        raise ValueError('Original engine, wheel, or attendance observation missing')
    return packet


class InstrumentClient:
    """One JSON-line request/response per CARLA tick, with no tick ownership."""

    def __init__(self, host, port, timeout_s=10):
        self.connection = socket.create_connection((host, port), timeout_s)
        self.connection.settimeout(timeout_s)
        self.reader = self.connection.makefile('r', encoding='utf-8')
        self.writer = self.connection.makefile('w', encoding='utf-8')

    def sample(self, native_frame, actor_id, wheel_angles_deg,
               actor_heading_world_deg=None):
        request = {'format': 'c276263-instrument-request-v1',
                   'native_frame': native_frame, 'actor_id': actor_id,
                   'native_front_wheel_angles_deg': wheel_angles_deg,
                   'actor_heading_world_deg': actor_heading_world_deg}
        self.writer.write(json.dumps(request, sort_keys=True) + '\n')
        self.writer.flush()
        line = self.reader.readline()
        if not line:
            raise ValueError('Original instrument service closed before frame response')
        return validate_packet(json.loads(line), native_frame, actor_id)

    def close(self):
        self.reader.close()
        self.writer.close()
        self.connection.close()
