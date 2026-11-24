"""Exercise 600-frame curb source measurements for both unselected requests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    manifest = json.loads((HERE / 'duration-probes/manifest.json').read_text())
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c230222-duration-source-'))
    results = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / 'duration-probes' / entry['construction']).read_text())
        # The source in the construction is the exact source exercised below.
        source = next(x['content'] for x in construction['files'] if x['path'] == 'curb.py')
        folder = root / suffix
        folder.mkdir()
        (folder / 'curb.py').write_text(source)
        spec = importlib.util.spec_from_file_location('curb_' + suffix, folder / 'curb.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        shutil.copy2(HERE / 'native/road.xodr', folder / 'road.xodr')
        departure = .5 if suffix == 'probe_1' else 3.5
        context = {
            'source_kind': 'synthetic_scene_request',
            'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
            'authored_road_sha256': sha(folder / 'road.xodr'),
            'pedestrian_id': 'proposed-pedestrian', 'vehicle_id': 'proposed-vehicle',
            'curb_edge_xy_m': [-3.5, 0], 'pedestrian_crossing_forward_xy': [1, 0],
            'road_width_m': 7, 'vehicle_conflict_y_m': 0,
            'vehicle_lane_center_x_m': -1.75, 'vehicle_body_half_width_m': 1,
            'assumed_driver_reaction_s': [0.8, 1.2],
            'assumed_deceleration_mps2': [3.0, 5.0],
        }
        (folder / 'curb-context.json').write_text(json.dumps(context, indent=2) + '\n')
        rows = []
        for index in range(600):
            time = index / 20
            x = -4.5 + (3 * (time - departure) if time >= departure else 0)
            rows.append({
                'native_frame': 100 + index, 'time_s': time,
                'pedestrian_id': context['pedestrian_id'], 'vehicle_id': context['vehicle_id'],
                'pedestrian_xy_m': [x, 0],
                'pedestrian_footprint_xy_m': [[x-.12, -.12], [x+.12, -.12],
                                              [x+.12, .12], [x-.12, .12]],
                'pedestrian_speed_mps': 3 if time >= departure else 0,
                'vehicle_xy_m': [-1.75, -18 + 4 * time], 'vehicle_speed_mps': 4,
            })
        samples = folder / 'curb-samples.jsonl'
        write_rows(samples, rows)
        result = module.measure(samples, folder / 'curb-context.json')
        expected = 'conditional_yield_possible' if suffix == 'probe_1' else 'conditional_yield_impossible'
        if result['original_frames'] != 600 or result['conditional_yield_relation'] != expected:
            raise ValueError('Unexpected conditional source result')
        negatives = []
        for label, changed in (
            ('missing-final-frame', rows[:-1]),
            ('wrong-footprint', [{**r, 'pedestrian_footprint_xy_m': [[999, 0], *r['pedestrian_footprint_xy_m'][1:]]} if i == 10 else r for i, r in enumerate(rows)]),
        ):
            bad = folder / (label + '.jsonl')
            write_rows(bad, changed)
            try:
                module.measure(bad, folder / 'curb-context.json')
            except ValueError as error:
                negatives.append({'label': label, 'error': str(error)})
            else:
                raise AssertionError('Damaged source accepted: ' + label)
        results.append({
            'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'measurement_source_sha256': sha(folder / 'curb.py'),
            'source_hashes': result['source_sha256'],
            'conditional_yield_relation': expected,
            'first_roadway_entry': result['first_roadway_entry'],
            'conditional_stopping_margin_range_m': result['conditional_stopping_margin_range_m'],
            'negative_rejections': negatives,
            'driver_capability_measured': False, 'legal_verdict_claimed': False,
        })
    summary = {'format': 'c230222-600-frame-source-measurement-v1',
               'retained_root': str(root), 'frames': 600, 'results': results,
               'scope': 'synthetic diagnostic only; no original Native motion or actual driver capability'}
    path = HERE / 'duration-probes/source-measurement-proof.json'
    path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'frames': 600, 'negative_rejections': 4}))


if __name__ == '__main__':
    main()
