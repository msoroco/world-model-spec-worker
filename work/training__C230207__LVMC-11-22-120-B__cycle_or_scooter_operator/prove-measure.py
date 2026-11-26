"""Source-shaped synthetic tests; these do not prove actual sign or road use."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = Path(tempfile.mkdtemp(prefix='c230207-measure-', dir=ROOT / '.runtime-work'))
sys.path.insert(0, str(HERE / 'native'))
from measure import measure
from finalize import finalize
from comparison_audit import audit as audit_comparison


def fixture(label, y, suffix):
    folder = SCRATCH / label
    folder.mkdir(exist_ok=True)
    poses = folder / 'bicycle-poses.jsonl'
    frame_map = folder / 'video_frames.jsonl'
    context = folder / 'restriction-context.json'
    context.write_text(json.dumps({
        'case_id': HERE.name + '__' + suffix,
        'target_surface': 'roadway' if suffix == 'probe_02' else 'shoulder',
        'rider_class': 'human_propelled_bicycle', 'wheel_characteristics_reviewed': True,
        'blueprint_id': 'vehicle.bh.crossbike',
        'sign_text': 'BICYCLES PROHIBITED ON ROADWAY', 'sign_id': '100',
        'sign_x_m': -45, 'native_sign_survey': {'id': '100'},
        'sign_orientation': 'positive_s',
        'physical_sign_pixels_verified': False,
        'city_traffic_engineer_designation_verified': False,
        'native_roadway_survey': [{'lane_id': -1}] * 3,
        'native_shoulder_survey': [{'lane_id': -2}] * 3,
        'roadway_xy_m': [[-60, -3.5], [60, -3.5], [60, 0], [-60, 0]],
        'fixture_only': True}) + '\n')
    with poses.open('w') as out, frame_map.open('w') as mapped:
        for i in range(600):
            out.write(json.dumps({'video_frame': i, 'native_frame': 1000+i,
                                  'time_s': i/20, 'rider_xy_m': [-50+i*.115, y],
                                  'rider_z_m': 1, 'velocity_xy_mps': [2.3, 0],
                                  'rider_blueprint_id': 'vehicle.bh.crossbike',
                                  'provenance': 'synthetic_native_sample'}) + '\n')
            mapped.write(json.dumps({'video_frame': i, 'native_frame': 1000+i,
                                     'time_s': i/20,
                                     'camera_native_frames': {name: 1000+i for name in
                                       ('overview', 'approach', 'reference_corner', 'driver_reference')}}) + '\n')
    (folder / 'config.json').write_text(json.dumps({
        'case_id': HERE.name + '__' + suffix,
        'recording_description': {'channels': []},
        'fixture_only': True}) + '\n')
    return poses, context


def reject(poses, context, expected):
    try:
        measure(poses, context)
    except ValueError as exc:
        assert expected in str(exc)
        return str(exc)
    raise AssertionError('missing source accepted')


def main():
    road_poses, road_context = fixture('roadway', -1.75, 'probe_02')
    shoulder_poses, shoulder_context = fixture('shoulder', -4.75, 'probe_01')
    road = measure(road_poses, road_context)
    shoulder = measure(shoulder_poses, shoulder_context)
    assert road['roadway_occupied_frames'] == 600
    assert road['roadway_occupied_after_sign_frames'] > 500
    assert shoulder['roadway_occupied_frames'] == 0
    lines = road_poses.read_text().splitlines()
    missing_frames = SCRATCH / 'missing-bicycle-poses.jsonl'
    missing_frames.write_text('\n'.join(lines[:-1]) + '\n')
    negative_frame = reject(missing_frames, road_context, 'missing original bicycle frames')
    context = json.loads(road_context.read_text())
    context.pop('native_sign_survey')
    missing_sign = SCRATCH / 'missing-sign.json'
    missing_sign.write_text(json.dumps(context) + '\n')
    negative_sign = reject(road_poses, missing_sign, 'Native sign or roadway survey source missing')
    context = json.loads(road_context.read_text())
    context['rider_class'] = 'scooter'
    wrong_class = SCRATCH / 'wrong-class.json'
    wrong_class.write_text(json.dumps(context) + '\n')
    negative_class = reject(road_poses, wrong_class, 'original bicycle actor source missing')
    road_report = finalize(road_poses.parent, road_poses.parent / 'analysis.json')
    shoulder_report = finalize(shoulder_poses.parent, shoulder_poses.parent / 'analysis.json')
    assert road_report['measurements']['measure']['value']['roadway_occupied_frames'] == 600
    assert shoulder_report['measurements']['measure']['value']['roadway_occupied_frames'] == 0
    comparison = audit_comparison(shoulder_poses.parent, road_poses.parent)
    assert comparison['passed'] and comparison['shoulder_roadway_frames'] == 0
    absent = SCRATCH / 'missing-frame-map'
    absent.mkdir(exist_ok=True)
    (absent / 'config.json').write_bytes((road_poses.parent / 'config.json').read_bytes())
    (absent / 'bicycle-poses.jsonl').write_bytes(road_poses.read_bytes())
    (absent / 'restriction-context.json').write_bytes(road_context.read_bytes())
    try:
        finalize(absent, absent / 'analysis.json')
    except ValueError as exc:
        assert 'Missing required source: video_frames.jsonl' in str(exc)
    else:
        raise AssertionError('finalizer accepted missing original frame map')
    corrupt = SCRATCH / 'wrong-camera-join'
    corrupt.mkdir(exist_ok=True)
    for name in ('config.json', 'bicycle-poses.jsonl', 'restriction-context.json',
                 'video_frames.jsonl'):
        (corrupt / name).write_bytes((road_poses.parent / name).read_bytes())
    frame_rows = (corrupt / 'video_frames.jsonl').read_text().splitlines()
    first = json.loads(frame_rows[0])
    first['camera_native_frames']['approach'] += 1
    frame_rows[0] = json.dumps(first)
    (corrupt / 'video_frames.jsonl').write_text('\n'.join(frame_rows) + '\n')
    try:
        finalize(corrupt, corrupt / 'analysis.json')
    except ValueError as exc:
        assert 'Original four-view frame join differs' in str(exc)
    else:
        raise AssertionError('finalizer accepted wrong original camera join')
    altered = SCRATCH / 'changed-sign-comparison'
    altered.mkdir(exist_ok=True)
    for name in ('bicycle-poses.jsonl', 'restriction-context.json', 'video_frames.jsonl'):
        (altered / name).write_bytes((shoulder_poses.parent / name).read_bytes())
    changed = json.loads((altered / 'restriction-context.json').read_text())
    changed['sign_text'] = 'NO BICYCLES ON SHOULDER'
    (altered / 'restriction-context.json').write_text(json.dumps(changed) + '\n')
    try:
        audit_comparison(altered, road_poses.parent)
    except ValueError as exc:
        assert 'exact bicycle sign source missing' in str(exc)
    else:
        raise AssertionError('comparison accepted changed sign')
    print(json.dumps({'passed': True, 'fixture_kind': 'synthetic_native_sample',
                      'roadway': road, 'shoulder': shoulder,
                      'negative_missing_frame': negative_frame,
                      'negative_missing_sign': negative_sign,
                      'negative_wrong_class': negative_class,
                      'finalizer_positive_cases': 2,
                      'finalizer_negative_missing_frame_map': True,
                      'finalizer_negative_wrong_camera_join': True,
                      'comparison_positive': comparison,
                      'comparison_negative_changed_sign': True,
                      'measure_sha256': hashlib.sha256((HERE/'native/measure.py').read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    main()
