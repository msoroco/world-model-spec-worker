"""Test the retained-source entry reducer with synthetic CPU packets."""
import argparse
import hashlib
import json
from pathlib import Path

import saved_entry

CASE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True).encode()


def source_packet(folder):
    track = [json.loads(line) for line in (folder / 'requested-track.jsonl').read_text().splitlines()]
    poses = []
    frames = []
    for row in track:
        mapped = {'video_frame': row['video_frame'], 'native_frame': row['native_frame'],
                  'time_s': row['time_s'],
                  'camera_native_frames': dict.fromkeys(saved_entry.CAMERAS, row['native_frame'])}
        pose = dict(mapped, vehicle_id='synthetic-ego', center_xy_m=row['center_xy_m'],
                    footprint_half_width_m=row['footprint_half_width_m'])
        poses.append(pose); frames.append(mapped)
    road = b'synthetic controlled-access road source for software proof'
    token = sha(b'synthetic authority source for software proof')
    context = {'assignment_id': CASE.name, 'source_kind': 'synthetic_cpu',
               'road_source_sha256': sha(road),
               'controlled_access_designation_sha256': token,
               'official_device_authority_sha256': token,
               'device_content_sha256': token,
               'device_erection_sha256': token,
               'entrance_extent_source_sha256': token,
               'controlled_access_highway': True, 'device_official': True,
               'device_erected': True, 'device_indicates_entry': True,
               'highway_road_id': 'synthetic-highway-1',
               'highway_edge_y_m': 0, 'indicated_entrance_x_interval_m': [-2.2, 2.2]}
    return poses, frames, context, road


def encoded_rows(rows):
    return b''.join(wire(row) + b'\n' for row in rows)


def rejected(poses, frames, context, road, label, negatives):
    try:
        saved_entry.measure(encoded_rows(poses), encoded_rows(frames), wire(context), road)
    except ValueError as error:
        negatives.append({'mutation': label, 'error': str(error)})
    else:
        raise AssertionError('altered source accepted: ' + label)


def prove(root):
    positives = []
    for witness, expected in (('witness_1', True), ('witness_2', False)):
        poses, frames, context, road = source_packet(root / witness)
        result = saved_entry.measure(encoded_rows(poses), encoded_rows(frames),
                                     wire(context), road)
        if (result['frame_count'] != 600 or result['four_camera_joins'] != 2400
                or len(result['entry_events']) != 1
                or result['entry_events'][0]['within_indicated_gate'] is not expected
                or result['legal_result'] is not None):
            raise AssertionError('controlled saved measurement differs')
        positives.append({'witness': witness, 'within_indicated_gate': expected,
                          'entry_frame': result['entry_events'][0]['video_frame'],
                          'pose_sha256': result['pose_sha256'],
                          'frame_map_sha256': result['frame_map_sha256']})
    negatives = []
    poses, frames, context, road = source_packet(root / 'witness_1')
    changed = json.loads(wire(context)); changed['official_device_authority_sha256'] = None
    rejected(poses, frames, changed, road, 'missing_official_authority_source', negatives)
    changed = json.loads(wire(context)); changed['device_indicates_entry'] = False
    rejected(poses, frames, changed, road, 'missing_device_entry_indication', negatives)
    changed = json.loads(wire(frames)); changed[250]['native_frame'] += 1
    rejected(poses, changed, context, road, 'altered_original_frame_map', negatives)
    changed = json.loads(wire(poses)); changed[250]['camera_native_frames']['highway_side'] += 1
    rejected(changed, frames, context, road, 'altered_fourth_camera_join', negatives)
    changed = json.loads(wire(poses)); changed[240]['center_xy_m'] = None
    rejected(changed, frames, context, road, 'missing_measured_position', negatives)
    changed = poses[:599]
    rejected(changed, frames[:599], context, road, 'short_recording', negatives)
    rejected(poses, frames, context, road + b'changed', 'changed_road_source', negatives)
    proof = {'format': 'c228131-saved-entry-cpu-proof-v1',
             'assignment_id': CASE.name, 'reducer_sha256': sha((CASE / 'saved_entry.py').read_bytes()),
             'input_sha256': sha((CASE.parents[1] / 'inputs' / CASE.name /
                                   'assignment.json').read_bytes()),
             'positives': positives, 'negatives': negatives,
             'source_kind': 'synthetic_cpu', 'original_native_observed': False,
             'official_device_authority_independently_reviewed': False,
             'physical_completion_verified': False, 'delivery_ready': False}
    path = CASE / 'saved-entry-proof.json'
    path.write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    result = prove(args.source_root)
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
