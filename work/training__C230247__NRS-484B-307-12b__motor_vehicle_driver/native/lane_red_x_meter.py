"""Source-bound engineering measurements for the individual-lane red X.

Lane intersection and motion are observations; this module issues no legal verdict.
"""
import math

ASSIGNMENT = 'training__C230247__NRS-484B-307-12b__motor_vehicle_driver'

def measure(packet):
    rows = packet['frames']
    if len(rows) != 600:
        raise ValueError('expected 600 source frames')
    observations = []
    first_native = None
    first_time = None
    for index, row in enumerate(rows):
        frame = row.get('native_frame')
        time_s = row.get('time_s')
        if type(frame) is not int or type(row.get('frame')) is not int or row['frame'] != index:
            raise ValueError('original frame identity absent')
        if first_native is None:
            first_native = frame
            first_time = time_s
        if frame != first_native + index or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError('original frame identity discontinuity')
        if abs((time_s - first_time) - index / 20) > .001:
            raise ValueError('source clock discontinuity')
        if row.get('source') != 'native_post_tick':
            raise ValueError('source frame provenance absent')
        signal = row.get('signal')
        vehicle = row.get('vehicle')
        if not isinstance(signal, dict) or not isinstance(vehicle, dict):
            raise ValueError('signal and vehicle source packets required')
        if signal.get('source') != 'native_signal_state' or signal.get('authority_source') != 'map_signal_inventory':
            raise ValueError('original signal provenance absent')
        if signal.get('id') != 100 or signal.get('lane_id') != -1 or signal.get('mount_lane_id') != -1:
            raise ValueError('original governed lane differs')
        if signal.get('mount_source') != 'map_signal_transform' or signal.get('inventory_verified') is not True:
            raise ValueError('overhead map signal source absent')
        if signal.get('official_authority_review_pending') is not True or signal.get('indication') != 'red_x':
            raise ValueError('original red-X state or review status absent')
        mount = signal.get('mount_m')
        if not isinstance(mount, list) or len(mount) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in mount):
            raise ValueError('original signal mount absent')
        if not (0 < mount[0] < 120 and -3.5 < mount[1] < 0 and mount[2] >= 4):
            raise ValueError('signal not mounted over governed lane')
        if vehicle.get('source') != 'native_actor_pose' or vehicle.get('lane_source') != 'map_waypoint_projection':
            raise ValueError('original actor body provenance absent')
        vertices = vehicle.get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) != 8 or any(
            not isinstance(v, list) or len(v) != 3 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in v)
            for v in vertices):
            raise ValueError('original actor body vertices absent')
        if vehicle.get('lane_id') not in (-1, -2) or vehicle.get('proposed_lane_id') not in (-1, -2):
            raise ValueError('original actor lane projection absent')
        yaw = vehicle.get('yaw_deg')
        facing = signal.get('facing_yaw_deg')
        if not isinstance(yaw, (int, float)) or not isinstance(facing, (int, float)):
            raise ValueError('driver and signal orientation absent')
        difference = abs((yaw - facing + 180) % 360 - 180)
        y_min = min(v[1] for v in vertices)
        y_max = max(v[1] for v in vertices)
        overlap = y_max > -3.5 and y_min < 0
        wholly_inside = y_min >= -3.5 and y_max <= 0
        observations.append({
            'frame': index, 'native_frame': frame, 'time_s': time_s,
            'signal_id': signal['id'], 'signal_lane_id': -1,
            'red_x': True, 'facing_signal': difference <= 30,
            'vehicle_lane_id': vehicle['lane_id'],
            'governed_lane_overlap': overlap, 'wholly_in_governed_lane': wholly_inside,
            'body_y_range_m': [y_min, y_max]
        })
    first_overlap = next((o['frame'] for o in observations if o['governed_lane_overlap']), None)
    return {
        'format': 'red-x-source-meter-v1', 'assignment_id': ASSIGNMENT,
        'frames': 600, 'rate_hz': 20,
        'red_x_facing_frames': sum(o['red_x'] and o['facing_signal'] for o in observations),
        'governed_lane_overlap_frames': sum(o['governed_lane_overlap'] for o in observations),
        'governed_lane_wholly_inside_frames': sum(o['wholly_in_governed_lane'] for o in observations),
        'first_governed_lane_overlap_frame': first_overlap,
        'observations': observations, 'physical_observation_claimed': False,
        'legal_conclusion': None
    }
