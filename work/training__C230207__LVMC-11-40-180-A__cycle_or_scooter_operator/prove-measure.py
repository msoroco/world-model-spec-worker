"""Source-shaped synthetic fixtures test joins and statutory distinctions."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c230207-180a-measure-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE / 'native'))
from geometry import SIGN_NAME
from measure import measure


def fixture(label, posture, y=-5, behavior='mounted_sidewalk'):
    folder = SCRATCH / label
    folder.mkdir(exist_ok=True)
    poses = folder / 'bicycle-poses.jsonl'
    frames = folder / 'video_frames.jsonl'
    context = folder / 'restriction-context.json'
    context.write_text(json.dumps({
        'rider_class': 'human_propelled_bicycle', 'blueprint_id': 'vehicle.bh.crossbike',
        'sign_text': SIGN_NAME, 'sign_id': '100', 'native_sign_survey': {'id': '100'},
        'native_sidewalk_survey': [{'lane_id': -2}] * 3,
        'sidewalk_xy_m': [[-60, -6.5], [60, -6.5], [60, -3.5], [-60, -3.5]],
        'street_name': 'Fremont Street', 'west_boundary': 'Main Street',
        'east_boundary': 'Seventh Street', 'geographic_identity_verified': False,
        'controlled_behavior': behavior,
        'operator_actor_id': 120 if behavior == 'walk_cycle' else None,
        'operator_blueprint_id': 'walker.pedestrian.0001' if behavior == 'walk_cycle' else None,
        'dismounted_association_max_separation_m': 1.5 if behavior == 'walk_cycle' else None,
        'physical_sign_pixels_verified': False, 'fixture_only': True}) + '\n')
    with poses.open('w') as p, frames.open('w') as f:
        for i in range(600):
            native = 1000 + i
            t = i / 20
            row = {'video_frame': i, 'native_frame': native, 'time_s': t,
                   'rider_xy_m': [-65 + i * .115, y], 'velocity_xy_mps': [2.3, 0],
                   'rider_blueprint_id': 'vehicle.bh.crossbike',
                   'machine_class': 'human_propelled_bicycle', 'mounted_posture': posture,
                   'operator_actor_id': 120 if behavior == 'walk_cycle' else None,
                   'operator_blueprint_id': 'walker.pedestrian.0001' if behavior == 'walk_cycle' else None,
                   'operator_xy_m': [-65 + i * .115, y + .8] if behavior == 'walk_cycle' else None,
                   'operator_velocity_xy_mps': [2.3, 0] if behavior == 'walk_cycle' else None,
                   'provenance': 'synthetic_native_sample'}
            frame = {'video_frame': i, 'native_frame': native, 'time_s': t,
                     'camera_native_frames': {name: native for name in
                        ('overview', 'sign_approach', 'sign_face', 'sidewalk_use')}}
            p.write(json.dumps(row) + '\n')
            f.write(json.dumps(frame) + '\n')
    return poses, context, frames


def reject(paths, expected):
    try:
        measure(*paths)
    except ValueError as exc:
        assert expected in str(exc), str(exc)
        return str(exc)
    raise AssertionError('missing source accepted')


def main():
    mounted_paths = fixture('mounted', 'mounted')
    dismounted_paths = fixture('dismounted', 'dismounted', behavior='walk_cycle')
    uncertain_paths = fixture('unverified', 'unverified')
    mounted = measure(*mounted_paths)
    dismounted = measure(*dismounted_paths)
    uncertain = measure(*uncertain_paths)
    assert mounted['mounted_moving_sidewalk_frames'] > 500
    assert dismounted['mounted_moving_sidewalk_frames'] == 0
    assert dismounted['dismounted_moving_sidewalk_frames'] > 500
    assert dismounted['operator_cycle_association_within_plan'] is True
    assert uncertain['posture_unverified_frames'] == 600
    assert uncertain['mounted_moving_sidewalk_frames'] == 0
    assert mounted['riding_prohibition_conditional_on_sign'] is False
    bad = SCRATCH / 'missing-frame.jsonl'
    bad.write_text('\n'.join(mounted_paths[0].read_text().splitlines()[:-1]) + '\n')
    missing_frame = reject((bad, *mounted_paths[1:]), 'missing original 600-frame source')
    context = json.loads(mounted_paths[1].read_text())
    context.pop('native_sidewalk_survey')
    bad_context = SCRATCH / 'missing-sidewalk.json'
    bad_context.write_text(json.dumps(context) + '\n')
    missing_sidewalk = reject((mounted_paths[0], bad_context, mounted_paths[2]), 'Native sidewalk geometry source missing')
    context = json.loads(mounted_paths[1].read_text())
    context['street_name'] = 'Another Street'
    bad_context = SCRATCH / 'wrong-street.json'
    bad_context.write_text(json.dumps(context) + '\n')
    wrong_street = reject((mounted_paths[0], bad_context, mounted_paths[2]), 'named segment source missing')
    context = json.loads(mounted_paths[1].read_text())
    context['rider_class'] = 'motorcycle'
    bad_context = SCRATCH / 'wrong-class.json'
    bad_context.write_text(json.dumps(context) + '\n')
    wrong_class = reject((mounted_paths[0], bad_context, mounted_paths[2]), 'covered machine class source missing')
    lines = mounted_paths[2].read_text().splitlines()
    frame = json.loads(lines[8])
    frame['camera_native_frames'].pop('sign_face')
    lines[8] = json.dumps(frame)
    bad_map = SCRATCH / 'missing-camera.jsonl'
    bad_map.write_text('\n'.join(lines) + '\n')
    missing_camera = reject((mounted_paths[0], mounted_paths[1], bad_map), 'four source camera frame join failed')
    context = json.loads(dismounted_paths[1].read_text())
    context.pop('operator_actor_id')
    bad_context = SCRATCH / 'missing-operator.json'
    bad_context.write_text(json.dumps(context) + '\n')
    missing_operator = reject((dismounted_paths[0], bad_context, dismounted_paths[2]), 'dismounted operator source missing')
    print(json.dumps({'passed': True, 'fixture_kind': 'synthetic_native_sample',
                      'mounted': mounted, 'dismounted': dismounted, 'unverified': uncertain,
                      'negative_missing_frame': missing_frame,
                      'negative_missing_sidewalk': missing_sidewalk,
                      'negative_wrong_street': wrong_street,
                      'negative_wrong_class': wrong_class,
                      'negative_missing_camera': missing_camera,
                      'negative_missing_operator': missing_operator,
                      'measure_sha256': hashlib.sha256((HERE/'native/measure.py').read_bytes()).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
