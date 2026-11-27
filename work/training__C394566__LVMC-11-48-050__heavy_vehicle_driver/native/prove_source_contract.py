"""Exercise full-frame source joins and missing/changed authority rejection."""
import json
import os
import sys
import tempfile
from pathlib import Path
from source_contract import load, sha
from route_measurement import evaluate

CASE = 'training__C394566__LVMC-11-48-050__heavy_vehicle_driver__truck_route'


def build(folder):
    refs = {}
    for name in ('weight', 'district', 'truck_route', 'civil_clock', 'permit'):
        path = folder / (name + '.source.json')
        path.write_text(json.dumps({'source_kind': 'synthetic_diagnostic', 'name': name}) + '\n')
        refs[name] = {'path': path.name, 'sha256': sha(path)}
    context = {'case_id': CASE, 'source_kind': 'synthetic_native_sample',
               'authority_refs': refs, 'facts': {'unladen_weight_lb': 8001,
               'district': 'residence', 'truck_route': True,
               'civil_timestamp': '2026-11-27T20:00:00-08:00',
               'written_permit_status': 'absent'}}
    (folder / 'source-context.json').write_text(json.dumps(context, sort_keys=True) + '\n')
    with (folder / 'original-route-rows.jsonl').open('w') as route, (folder / 'video_frames.jsonl').open('w') as frames:
        for i in range(600):
            frame = i + 100
            route.write(json.dumps({'case_id': CASE, 'source_kind': 'original_native_pose',
                                    'video_frame': i, 'native_frame': frame, 'time_s': i / 20,
                                    'road_id': 12, 'ego_speed_mps': 3.2, 'ego_x_m': i / 10, 'ego_y_m': 0.0, 'vehicle_half_extent_m': [3.0, 1.2]}) + '\n')
            frames.write(json.dumps({'video_frame': i, 'native_frame': frame, 'time_s': i / 20}) + '\n')
    names = ('source-context.json', 'original-route-rows.jsonl', 'video_frames.jsonl')
    (folder / 'capture-seal.json').write_text(json.dumps({'case_id': CASE,
        'sha256': {name: sha(folder / name) for name in names}}, sort_keys=True) + '\n')


def rejected(folder, expected):
    try:
        load(folder, CASE)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Altered original source was accepted')


def main():
    root = Path(os.environ.get('TMPDIR', '.runtime-work'))
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c394566-source-proof-') as temporary:
        folder = Path(temporary)
        build(folder)
        receipt = load(folder, CASE)
        assert receipt['frame_count'] == 600 and receipt['source_kind'] == 'synthetic_native_sample'
        observed = evaluate(folder, CASE)
        assert observed['factual_measurements']['vehicle_over_8000_lb'] is True
        assert observed['factual_measurements']['night_window'] == 'inside'
        assert observed['factual_measurements']['non_truck_route'] is False
        assert observed['factual_measurements']['observed_movement'] is True
        (folder / 'weight.source.json').unlink()
        missing = rejected(folder, 'Missing or changed authority source: weight')
        build(folder)
        rows = (folder / 'original-route-rows.jsonl').read_text().splitlines()
        changed = json.loads(rows[211]); changed['native_frame'] += 1; rows[211] = json.dumps(changed)
        (folder / 'original-route-rows.jsonl').write_text('\n'.join(rows) + '\n')
        changed_source = rejected(folder, 'Original source seal differs')
        build(folder)
        rows = (folder / 'original-route-rows.jsonl').read_text().splitlines()
        changed = json.loads(rows[211]); changed['native_frame'] += 1; rows[211] = json.dumps(changed)
        (folder / 'original-route-rows.jsonl').write_text('\n'.join(rows) + '\n')
        seal = json.loads((folder / 'capture-seal.json').read_text())
        seal['sha256']['original-route-rows.jsonl'] = sha(folder / 'original-route-rows.jsonl')
        (folder / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
        broken_join = rejected(folder, 'Native route/frame join differs')
        print(json.dumps({'positive_join_frames': receipt['frame_count'],
            'missing_authority_rejected': missing, 'changed_source_rejected': changed_source,
            'broken_join_rejected': broken_join, 'original_review_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    sys.exit(main())
