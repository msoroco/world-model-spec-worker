"""Unselected synthetic curb-departure and vehicle-approach source comparison."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from curb import measure, sha


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c230222-curb-'))
    records = []
    for suffix, departure, expected in (
        ('probe_1', .5, 'conditional_yield_possible'),
        ('probe_2', 3.5, 'conditional_yield_impossible'),
    ):
        folder = root / suffix
        folder.mkdir()
        shutil.copy2(HERE / 'native/road.xodr', folder / 'road.xodr')
        context = {'format': 'c230222-curb-synthetic-context-v1',
                   'source_kind': 'synthetic_scene_request',
                   'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
                   'authored_road_sha256': sha(folder / 'road.xodr'),
                   'native_road_sha256': None, 'vehicle_source_audit_sha256': None,
                   'pedestrian_id': 'C230222-proposed-pedestrian',
                   'vehicle_id': 'C230222-proposed-approaching-vehicle',
                   'curb_edge_xy_m': [-3.5, 0], 'pedestrian_crossing_forward_xy': [1, 0],
                   'road_width_m': 7, 'vehicle_conflict_y_m': 0,
                   'vehicle_lane_center_x_m': -1.75, 'vehicle_body_half_width_m': 1,
                   'assumed_driver_reaction_s': [0.8, 1.2],
                   'assumed_deceleration_mps2': [3.0, 5.0],
                   'driver_capability_source': 'assumption_only_not_original_vehicle_measurement',
                   'introductory_exceptions': 'unreviewed_synthetic_context',
                   'requested_pedestrian_departure_s': departure}
        (folder / 'curb-context.json').write_text(json.dumps(context, indent=2) + '\n')
        rows = []
        for index in range(240):
            time = index/20
            x = -4.5 + (3*(time-departure) if time >= departure else 0)
            body = [[x-.12, -.12], [x+.12, -.12], [x+.12, .12], [x-.12, .12]]
            rows.append({'native_frame': 100+index, 'time_s': time,
                         'pedestrian_id': context['pedestrian_id'],
                         'vehicle_id': context['vehicle_id'],
                         'pedestrian_xy_m': [x, 0],
                         'pedestrian_footprint_xy_m': body,
                         'pedestrian_speed_mps': 3 if time >= departure else 0,
                         'vehicle_xy_m': [-1.75, -18+4*time],
                         'vehicle_speed_mps': 4,
                         'source_scope': 'authored synthetic motion and assumed driver response'})
        write_rows(folder / 'curb-samples.jsonl', rows)
        measured = measure(folder / 'curb-samples.jsonl', folder / 'curb-context.json')
        if measured['conditional_yield_relation'] != expected:
            raise RuntimeError('Synthetic curb margin missed requested relation')
        (folder / 'source-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        negatives = []
        for label, expected_error in (
            ('missing', 'Missing required source: curb-samples.jsonl'),
            ('bad-footprint', 'Curb pedestrian pose/footprint differs'),
            ('wrong-cell', 'Frozen curb cell differs'),
        ):
            bad = root / (suffix + '-' + label)
            shutil.copytree(folder, bad)
            (bad / 'source-measurement.json').unlink()
            if label == 'missing':
                (bad / 'curb-samples.jsonl').unlink()
            elif label == 'wrong-cell':
                changed = dict(context)
                changed['frozen_cell'] = {**context['frozen_cell'], 'control': 'crosswalk'}
                (bad / 'curb-context.json').write_text(json.dumps(changed) + '\n')
            else:
                changed = [dict(row) for row in rows]
                changed[10]['pedestrian_footprint_xy_m'] = [list(v) for v in changed[10]['pedestrian_footprint_xy_m']]
                changed[10]['pedestrian_footprint_xy_m'][0][0] += 1
                write_rows(bad / 'curb-samples.jsonl', changed)
            try:
                measure(bad / 'curb-samples.jsonl', bad / 'curb-context.json')
            except ValueError as error:
                if expected_error not in str(error):
                    raise
                negatives.append(str(error))
            else:
                raise RuntimeError('Damaged curb source accepted: ' + label)
        records.append({'case_suffix': suffix, 'case_id': HERE.name + '__' + suffix,
                        'retained_positive': str(folder), 'requested_departure_s': departure,
                        'conditional_yield_relation': expected, 'frames': 240,
                        'source_hashes': measured['source_sha256'],
                        'source_measurement_sha256': sha(folder / 'source-measurement.json'),
                        'negative_errors': negatives,
                        'scope': 'synthetic conditional stopping margins; no actual driver or legal finding'})
    (HERE / 'curb-summary.json').write_text(json.dumps({
        'format': 'c230222-curb-synthetic-proof-v1', 'retained_root': str(root),
        'records': records}, indent=2) + '\n')
    print(json.dumps({'controlled_cases': 2, 'frames_per_case': 240,
                      'negative_rejections': 6, 'impossibility_to_yield_proven': False,
                      'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
