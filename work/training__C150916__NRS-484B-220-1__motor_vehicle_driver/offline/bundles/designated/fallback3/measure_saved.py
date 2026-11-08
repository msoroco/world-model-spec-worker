"""Measure source-bound one-way lane and motion observations, without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FILES = ('native-observed.jsonl', 'road-readback.json',
         'sign-frames.jsonl', 'designation-record.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(folder, expected_hashes=None):
    folder = Path(folder)
    hashes = {name: sha(folder/name) for name in FILES}
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError('Saved one-way source hashes differ')
    rows = load_rows(folder/'native-observed.jsonl')
    signs = load_rows(folder/'sign-frames.jsonl')
    road = json.loads((folder/'road-readback.json').read_text())
    designation = json.loads((folder/'designation-record.json').read_text())
    if len(rows) != 240 or len(signs) != 240:
        raise ValueError('Saved one-way row count differs')
    source_kind = rows[0].get('source_kind')
    if source_kind not in ('synthetic_cpu', 'original_native') or any(
            row.get('source_kind') != source_kind for row in rows+signs):
        raise ValueError('Saved one-way source kinds differ')
    if (road.get('source_kind') != source_kind or
            sorted(road.get('driving_lane_ids', [])) != [-2,-1] or
            road.get('lane_direction_x') != 1 or
            road.get('sign_requests') != {'101': {'type':'R6-1','direction_x':1},
                                          '102': {'type':'R6-1','direction_x':1}} or
            designation.get('source_kind') != source_kind or
            designation.get('designated_direction_x') != 1 or
            designation.get('status') not in ('synthetic_unverified','review_pending')):
        raise ValueError('Saved one-way road, sign or designation readback differs')
    if source_kind == 'original_native' and (not designation.get('source_sha256') or
                                            designation.get('status') != 'review_pending'):
        raise ValueError('Original designation source reference absent')
    case = rows[0].get('case')
    if case not in ('designated','opposite') or any(row.get('case') != case for row in rows):
        raise ValueError('Saved one-way case identity differs')
    expected_heading = 0 if case == 'designated' else 180
    expected_direction = 1 if case == 'designated' else -1
    sign_visible = {101: 0, 102: 0}
    occupied = 0
    for i, (row, sign) in enumerate(zip(rows, signs)):
        t = (i+1)/20
        if any(not isinstance(row.get(key), (int,float)) or not math.isfinite(row[key])
               for key in ('time_s','ego_x_m','ego_y_m','ego_speed_mps','ego_velocity_x_mps')) or \
           not isinstance(sign.get('time_s'), (int,float)) or not math.isfinite(sign['time_s']):
            raise ValueError('Saved one-way numeric observation invalid')
        if (row.get('frame') != i or sign.get('frame') != i or
                abs(row.get('time_s', float('nan'))-t) > 1e-6 or
                abs(sign.get('time_s', float('nan'))-t) > 1e-6 or
                row.get('native_frame') != sign.get('native_frame') or
                row.get('lane_id') not in (-2,-1) or
                abs(row.get('ego_y_m', float('nan'))-(-1.75 if row['lane_id']==-1 else -5.25)) > .35 or
                row.get('ego_heading_deg') != expected_heading or
                not math.isfinite(row.get('ego_x_m', float('nan'))) or
                not math.isfinite(row.get('ego_speed_mps', float('nan'))) or
                row['ego_speed_mps'] < 0 or
                abs(row.get('ego_velocity_x_mps', float('nan'))-expected_direction*row['ego_speed_mps']) > .1):
            raise ValueError('Saved one-way frame, lane or kinematic join differs')
        if source_kind == 'original_native' and (not row.get('ego_body_vertices_m') or
                                                sign.get('camera_frame') != row['native_frame']):
            raise ValueError('Original one-way body or sign camera join absent')
        visible = sign.get('visible_sign_ids')
        if not isinstance(visible, list) or any(value not in (101,102) for value in visible):
            raise ValueError('Saved one-way sign frame differs')
        for value in set(visible): sign_visible[value] += 1
        if i:
            displacement = row['ego_x_m']-rows[i-1]['ego_x_m']
            expected = row['ego_velocity_x_mps']/20
            if abs(displacement-expected) > .11:
                raise ValueError('Saved one-way motion and velocity differ')
        if -100 <= row['ego_x_m'] <= 300:
            occupied += 1
    signed_distance = round(rows[-1]['ego_x_m']-rows[0]['ego_x_m'],3)
    if signed_distance*expected_direction <= 0 or occupied != 240:
        raise ValueError('Saved one-way traverse absent or outside road')
    return {'format':'c150916-saved-one-way-measurement-v1',
            'case':case,'source_kind':source_kind,'source_hashes':hashes,
            'frames':240,'occupied_frames':occupied,
            'signed_ego_displacement_m':signed_distance,
            'movement_direction_x':expected_direction,
            'designated_direction_x':designation['designated_direction_x'],
            'direction_matches_designation':expected_direction==designation['designated_direction_x'],
            'visible_sign_frame_counts':{str(key):value for key,value in sign_visible.items()},
            'designation_authority_verified':False,
            'physical_sign_verified':False,
            'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(measure(args.folder),indent=2))
