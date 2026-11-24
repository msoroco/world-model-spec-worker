"""Exercise saved-source measurement with clearly synthetic diagnostic fixtures."""
import json
import tempfile
from pathlib import Path

from measure_aisle import CAMERAS, measure


def write_fixture(path, inside, reviewed=True):
    path.mkdir()
    context = {'source_kind': 'original_native', 'cell_id': 'C200542',
               'access_aisle': {'x_min_m': 0, 'x_max_m': 7, 'y_min_m': -8, 'y_max_m': -4},
               'premises_public_access_reviewed': reviewed,
               'access_aisle_designation_reviewed': reviewed,
               'fixture_kind': 'synthetic_diagnostic_only'}
    (path / 'aisle-context.json').write_text(json.dumps(context) + '\n')
    y = -6 if inside else -2
    with (path / 'native-vehicle.jsonl').open('w') as motion, (path / 'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native = index + 100
            x = -20 + min(index, 120) * .2
            corners = [[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]
            motion.write(json.dumps({'native_frame': native, 'video_frame': index,
                'time_s': index/20, 'body_xy_m': corners,
                'speed_mps': 4 if index < 120 else 0}) + '\n')
            frames.write(json.dumps({'native_frame': native, 'video_frame': index,
                'time_s': index/20,
                'camera_native_frames': {name: native for name in CAMERAS}}) + '\n')
    for name in CAMERAS:
        (path / (name + '.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outside, inside, unreviewed = (root / x for x in ('outside','inside','unreviewed'))
        write_fixture(outside, False)
        write_fixture(inside, True)
        write_fixture(unreviewed, True, False)
        a, b = measure(outside), measure(inside)
        assert a['stationary_overlap_samples'] == 0
        assert b['stationary_overlap_samples'] == 480
        assert b['parked_classification'] == 'requires_independent_source_review'
        try:
            measure(unreviewed)
        except ValueError as error:
            assert 'designation not established' in str(error)
        else:
            raise AssertionError('Unreviewed designation accepted')
        (inside / 'parking_bay.mkv').unlink()
        try:
            measure(inside)
        except ValueError as error:
            assert 'Missing required source' in str(error)
        else:
            raise AssertionError('Missing camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed': True,
            'outside_stationary_overlap_samples': a['stationary_overlap_samples'],
            'inside_stationary_overlap_samples': b['stationary_overlap_samples'],
            'unreviewed_designation_rejected': True, 'missing_camera_rejected': True,
            'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
