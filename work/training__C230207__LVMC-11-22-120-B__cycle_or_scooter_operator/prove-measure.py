"""Source-shaped synthetic tests; these do not prove actual sign or road use."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c230207-measure-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE / 'native'))
from measure import measure


def fixture(label, y):
    folder = SCRATCH / label
    folder.mkdir(exist_ok=True)
    poses = folder / 'bicycle-poses.jsonl'
    context = folder / 'restriction-context.json'
    context.write_text(json.dumps({
        'rider_class': 'human_propelled_bicycle', 'wheel_characteristics_reviewed': True,
        'sign_text': 'BICYCLES PROHIBITED ON ROADWAY', 'sign_id': '100',
        'sign_x_m': -45, 'native_sign_survey': {'id': '100'},
        'native_roadway_survey': [{'lane_id': -1}] * 3,
        'roadway_xy_m': [[-60, -3.5], [60, -3.5], [60, 0], [-60, 0]],
        'fixture_only': True}) + '\n')
    with poses.open('w') as out:
        for i in range(600):
            out.write(json.dumps({'video_frame': i, 'native_frame': 1000+i,
                                  'time_s': i/20, 'rider_xy_m': [-50+i*.115, y],
                                  'provenance': 'synthetic_native_sample'}) + '\n')
    return poses, context


def reject(poses, context, expected):
    try:
        measure(poses, context)
    except ValueError as exc:
        assert expected in str(exc)
        return str(exc)
    raise AssertionError('missing source accepted')


def main():
    road_poses, road_context = fixture('roadway', -1.75)
    shoulder_poses, shoulder_context = fixture('shoulder', -4.75)
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
    negative_class = reject(road_poses, wrong_class, 'sourced bicycle subtype missing')
    print(json.dumps({'passed': True, 'fixture_kind': 'synthetic_native_sample',
                      'roadway': road, 'shoulder': shoulder,
                      'negative_missing_frame': negative_frame,
                      'negative_missing_sign': negative_sign,
                      'negative_wrong_class': negative_class,
                      'measure_sha256': hashlib.sha256((HERE/'native/measure.py').read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    main()
