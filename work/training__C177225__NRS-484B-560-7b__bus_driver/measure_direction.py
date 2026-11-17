"""Derive value-free observations from retained C177225 raw source rows.

The caller must read these rows from saved acquisition, not a fixture-provided
derived channels directory. Results describe motion and communication only;
they do not decide whether NRS 484B.560(7)(b) was violated.
"""
from math import isfinite

from officer_direction import Crossing, OfficerStop


def _frames(rows, name):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Missing raw ' + name)
    frames = [row.get('native_frame') for row in rows]
    if any(type(frame) is not int or frame < 0 for frame in frames):
        raise ValueError('Invalid raw ' + name + ' frame')
    if frames != sorted(set(frames)):
        raise ValueError('Raw ' + name + ' frames are not unique and ordered')
    return frames


def derive_observation(layout, signal, bus_rows, signal_rows, frame_map_rows,
                       *, source_kind):
    layout.validate()
    signal.validate()
    if source_kind not in ('original_native', 'synthetic_native_sample'):
        raise ValueError('Raw source provenance must be explicit')
    bus_frames = _frames(bus_rows, 'bus')
    signal_frames = _frames(signal_rows, 'officer signal')
    map_frames = _frames(frame_map_rows, 'video frame map')
    if bus_frames != signal_frames or bus_frames != map_frames:
        raise ValueError('Bus, direction and video frame map are not synchronized')
    if not any(signal.first_governing_frame <= frame <= signal.last_governing_frame
               for frame in bus_frames):
        raise ValueError('No recorded frame within governing direction interval')
    stop_line = layout.stop_station(signal.direction)
    near_rail = layout.track_center_m - signal.direction * layout.track_half_width_m
    witnessed = []
    stopped = []
    crossed = []
    speed_samples = []
    for bus, officer, mapping in zip(bus_rows, signal_rows, frame_map_rows):
        frame = bus['native_frame']
        if mapping.get('carla_frame') != frame:
            raise ValueError('Camera frame does not identify the same Native frame')
        if bus.get('actor_id') != signal.bus_id:
            raise ValueError('Raw bus actor differs from direction recipient')
        station = bus.get('station_m')
        velocity = bus.get('velocity_native_xyz_mps')
        if (not isinstance(station, (int, float)) or not isfinite(station) or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(isinstance(value, (int, float)) and isfinite(value)
                        for value in velocity)):
            raise ValueError('Missing raw Native bus station or velocity')
        speed = sum(value * value for value in velocity) ** 0.5
        speed_samples.append(speed)
        expected_active = signal.first_governing_frame <= frame <= signal.last_governing_frame
        if (officer.get('native_frame') != frame or
                officer.get('actor_id') != signal.officer_id or
                officer.get('recipient_actor_id') != signal.bus_id or
                officer.get('crossing_id') != signal.crossing_id or
                officer.get('direction') != signal.direction or
                officer.get('authorized') is not True or
                officer.get('hand_signal') != signal.hand_signal or
                officer.get('governing') is not expected_active):
            raise ValueError('Raw officer direction lacks authorization, scope or timing')
        if expected_active:
            witnessed.append(frame)
            front_station = station + signal.direction * layout.bus_length_m / 2
            if signal.direction * (stop_line - front_station) >= 0 and speed <= 0.05:
                stopped.append(frame)
            if signal.direction * (front_station - near_rail) >= 0:
                crossed.append(frame)
    return {
        'source_kind': source_kind,
        'case_observations_only': True,
        'native_frames': len(bus_frames),
        'officer_direction_witnessed_frames': witnessed,
        'stopped_before_line_frames': stopped,
        'crossed_near_rail_frames': crossed,
        'minimum_recorded_speed_mps': min(speed_samples),
        'observed_complete_stop_before_line': bool(stopped),
        'observed_crossing_entry': bool(crossed),
        'legal_verdict': None,
    }
