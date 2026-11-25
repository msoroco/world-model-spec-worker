"""Exercise source-bound saved measurement without claiming Native evidence."""
import hashlib
import json
from pathlib import Path

import parking_saved_measure as reducer

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True).encode()


def fixture(permission, kind='synthetic_native_sample'):
    source_hash = sha(b'synthetic source for CPU diagnostic')
    context = {'assignment_id': ASSIGNMENT, 'source_kind': kind,
               'road_id': '1', 'map_source_sha256': source_hash,
               'one_way_designation_source_sha256': source_hash,
               'street_boundary_source_sha256': source_hash,
               'device_inventory_source_sha256': source_hash,
               'device_authority_source_sha256': source_hash if permission else None,
               'device_content_source_sha256': source_hash if permission else None,
               'device_erection_source_sha256': source_hash if permission else None,
               'device_governance_source_sha256': source_hash if permission else None,
               'roadway_is_laned': True, 'roadway_is_one_way': True,
               'permission_device_present': permission,
               'device_official': permission, 'device_erected': permission,
               'notice_permits_left_standing_or_parking': permission,
               'device_governs_road_id': '1' if permission else None,
               'device_id': '497' if permission else None,
               'centerline_origin_xy_m': [0, 0], 'permitted_direction_xy': [1, 0],
               'street_half_width_m': 6.5}
    frames = []
    for i in range(600):
        y = -1.75 if i < 200 else 2.0
        frames.append({'video_frame': i, 'time_s': i / 20, 'native_frame': i + 1000,
                       'camera_native_frames': dict.fromkeys(reducer.CAMERAS, i + 1000),
                       'vehicle_id': 'synthetic-ego', 'speed_mps': 2 if i < 300 else 0,
                       'footprint_corners_xy_m': [[10, y - .5], [14, y - .5],
                                                  [14, y + .5], [10, y + .5]]})
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': kind,
              'vehicle_id': 'synthetic-ego', 'frames': frames}
    return packet, context


def reject(packet, context, label, negatives):
    try:
        reducer.measure(wire(packet), wire(context))
    except ValueError as error:
        negatives.append({'mutation': label, 'error': str(error)})
    else:
        raise AssertionError('altered source accepted: ' + label)


def main():
    positives = []
    for permission in (False, True):
        packet, context = fixture(permission)
        result = reducer.measure(wire(packet), wire(context))
        assert result['frame_count'] == 600 and result['duration_s'] == 30
        assert len(result['fully_left_rest_candidate_frames']) == 300
        assert result['permission_device_sourced'] is permission
        assert result['legal_result'] is None
        positives.append({'permission_device_sourced': permission,
                          'packet_sha256': result['packet_sha256'],
                          'context_sha256': result['context_sha256'],
                          'fully_left_rest_candidate_frames': 300})
    negatives = []
    packet, context = fixture(True)
    changed = json.loads(wire(context)); changed['device_authority_source_sha256'] = None
    reject(packet, changed, 'missing_device_authority_source', negatives)
    changed = json.loads(wire(context)); changed['device_governs_road_id'] = '2'
    reject(packet, changed, 'non_governing_permission_device', negatives)
    changed = json.loads(wire(packet)); changed['frames'][280]['camera_native_frames']['reference_corner'] += 1
    reject(changed, context, 'changed_third_camera_join', negatives)
    changed = json.loads(wire(packet)); changed['frames'][310]['footprint_corners_xy_m'] = None
    reject(changed, context, 'missing_footprint', negatives)
    changed = json.loads(wire(packet)); changed['frames'] = changed['frames'][:599]
    reject(changed, context, 'short_recording', negatives)
    packet, context = fixture(False)
    changed = json.loads(wire(context)); changed['device_inventory_source_sha256'] = None
    reject(packet, changed, 'missing_absence_inventory', negatives)
    changed = json.loads(wire(context)); changed['permission_device_present'] = True
    reject(packet, changed, 'invented_permission_without_authority', negatives)
    raw_map = b'synthetic source for CPU diagnostic'
    packet, context = fixture(True, 'native_saved_sample')
    pose_bytes = b''.join(wire(row) + b'\n' for row in packet['frames'])
    frame_bytes = b''.join(wire({key: row[key] for key in
                                ('video_frame', 'native_frame', 'camera_native_frames', 'time_s')}) + b'\n'
                           for row in packet['frames'])
    result = reducer.measure_original(pose_bytes, frame_bytes, wire(context), raw_map)
    assert result['original_pose_sha256'] == sha(pose_bytes)
    positives.append({'original_path_synthetic_source': True,
                      'pose_sha256': result['original_pose_sha256'],
                      'frame_map_sha256': result['original_frame_map_sha256']})
    corrupted = frame_bytes.splitlines()
    row = json.loads(corrupted[201]); row['native_frame'] += 1
    corrupted[201] = wire(row)
    try:
        reducer.measure_original(pose_bytes, b'\n'.join(corrupted) + b'\n',
                                 wire(context), raw_map)
    except ValueError as error:
        negatives.append({'mutation': 'changed_original_frame_map', 'error': str(error)})
    else:
        raise AssertionError('altered original frame map accepted')
    proof = {'format': 'nrs-484b-497-saved-cpu-proof-v1',
             'assignment_id': ASSIGNMENT, 'input_sha256': sha((HERE.parents[1] / 'inputs' /
                                                               ASSIGNMENT / 'assignment.json').read_bytes()),
             'reducer_sha256': sha((HERE / 'parking_saved_measure.py').read_bytes()),
             'positives': positives, 'negatives': negatives,
             'source_kind': 'synthetic_native_sample', 'original_native_observed': False,
             'physical_completion_verified': False, 'legal_result': None,
             'delivery_ready': False}
    path = HERE / 'parking-saved-proof.json'
    path.write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'positives': len(positives), 'negatives': len(negatives),
                      'proof_sha256': sha(path.read_bytes())}))


if __name__ == '__main__':
    main()
