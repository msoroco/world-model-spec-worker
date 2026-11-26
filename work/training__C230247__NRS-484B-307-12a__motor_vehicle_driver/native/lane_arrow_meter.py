"""Source-bound engineering meter for overhead lane-arrow permission.

No legal conclusion is inferred from a lane mismatch or an absent arrow.
"""
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'training__C230247__NRS-484B-307-12a__motor_vehicle_driver'
SOURCE = 'native_post_tick'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(packet):
    rows = packet['frames']
    if len(rows) != 600:
        raise ValueError('expected 600 source frames')
    observed = []
    first_native_frame = None
    for i, row in enumerate(rows):
        native_frame = row.get('native_frame')
        if type(native_frame) is not int:
            raise ValueError('original frame identity absent')
        if first_native_frame is None:
            first_native_frame = native_frame
        if row.get('frame') != i or native_frame != first_native_frame+i:
            raise ValueError('original frame identity discontinuity')
        if row.get('source') != SOURCE:
            raise ValueError('source frame provenance absent')
        if not isinstance(row.get('time_s'), (int,float)) or not math.isfinite(row['time_s']):
            raise ValueError('source clock absent')
        if i and abs((row['time_s']-rows[0]['time_s'])-i/20) > 0.001:
            raise ValueError('source clock discontinuity')
        signal = row.get('signal')
        vehicle = row.get('vehicle')
        if not isinstance(signal, dict) or not isinstance(vehicle, dict):
            raise ValueError('signal and vehicle source packets required')
        if signal.get('source') != 'native_signal_state' or signal.get('authority_source') != 'map_signal_inventory':
            raise ValueError('signal state or authority provenance absent')
        if signal.get('mount_source') != 'map_signal_transform':
            raise ValueError('overhead mount provenance absent')
        if type(signal.get('id')) is not int or not signal.get('authority_verified'):
            raise ValueError('official signal authority unverified')
        mount = signal.get('mount_m')
        if not isinstance(mount, list) or len(mount)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in mount):
            raise ValueError('signal mount position absent')
        if signal.get('lane_id') not in (-1, -2) or signal.get('mount_lane_id') != signal.get('lane_id'):
            raise ValueError('overhead signal-to-lane mapping absent')
        if vehicle.get('source') != 'native_actor_pose' or vehicle.get('lane_source') != 'map_waypoint_projection':
            raise ValueError('vehicle pose or lane provenance absent')
        vertices = vehicle.get('body_vertices_m')
        if not isinstance(vertices,list) or len(vertices)!=8 or any(not isinstance(v,list) or len(v)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in v) for v in vertices):
            raise ValueError('original actor body vertices absent')
        yaw = vehicle.get('yaw_deg')
        facing = signal.get('facing_yaw_deg')
        if not all(isinstance(x, (int,float)) and math.isfinite(x) for x in (yaw,facing)):
            raise ValueError('facing orientation absent')
        difference = abs((yaw-facing+180) % 360 - 180)
        state = signal.get('indication')
        if state not in ('green_down_arrow','red_x','dark'):
            raise ValueError('unsupported indication')
        lane = vehicle.get('lane_id')
        if lane not in (-1,-2):
            raise ValueError('occupied lane absent')
        proposed = vehicle.get('proposed_lane_id')
        if proposed not in (-1,-2):
            raise ValueError('proposed lane absent')
        observed.append({
            'frame':i, 'native_frame':row['native_frame'], 'time_s':row['time_s'],
            'indication':state, 'signal_lane_id':signal['lane_id'],
            'occupied_lane_id':lane, 'proposed_lane_id':proposed,
            'signal_id':signal['id'], 'signal_mount_m':mount,
            'facing_signal':difference <= 30.0,
            'green_over_proposed_lane':state == 'green_down_arrow' and signal['lane_id'] == proposed,
            'green_over_occupied_lane':state == 'green_down_arrow' and signal['lane_id'] == lane,
        })
    return {
        'format':'lane-arrow-source-meter-v1', 'assignment_id':ASSIGNMENT,
        'frames':len(observed), 'rate_hz':20,
        'facing_green_proposed_frames':sum(r['facing_signal'] and r['green_over_proposed_lane'] for r in observed),
        'facing_green_occupied_frames':sum(r['facing_signal'] and r['green_over_occupied_lane'] for r in observed),
        'red_x_frames':sum(r['indication']=='red_x' for r in observed),
        'observations':observed,
        'legal_conclusion':'none; permission under 12(a) is not a prohibition for another lane',
        'physical_observation_claimed':False,
    }


def measure_file(path):
    path = Path(path)
    result = measure(json.loads(path.read_text()))
    result['source_packet_path'] = str(path)
    result['source_packet_sha256'] = digest(path)
    return result
