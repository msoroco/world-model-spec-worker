"""Exercise the 600-frame source contract with synthetic CPU fixtures only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
NATIVE = FOLDER / 'native'
sys.path.insert(0, str(NATIVE))
from geometry import body, open_drive  # noqa: E402
from measure_delivery_gap import FRAMES, RATE_HZ, measure  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(folder):
    names = ('native_samples.jsonl', 'following_context.json', 'road.xodr')
    (folder / 'source-manifest.json').write_text(json.dumps({
        'format': 'c102372-truck-follow-source-v1',
        'sha256': {name: sha(folder / name) for name in names}}, sort_keys=True) + '\n')


def write_case(folder, gap_m):
    folder.mkdir()
    rows = []
    for frame in range(FRAMES):
        ego_x = 20 + 8 * frame / RATE_HZ
        lead_x = ego_x + 12 + gap_m
        rows.append({'native_frame': frame, 'time_s': frame / RATE_HZ,
                     'ego': {'actor_class': 'truck_or_combination', 'road_id': 1,
                             'lane_id': -1, 'speed_mps': 8, 'body_xy_m': body(ego_x)},
                     'lead': {'actor_class': 'truck_or_combination', 'road_id': 1,
                              'lane_id': -1, 'speed_mps': 8, 'body_xy_m': body(lead_x)}})
    (folder / 'native_samples.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    (folder / 'following_context.json').write_text(json.dumps({
        'source_kind': 'synthetic_cpu_fixture', 'road_id': 1, 'lane_id': -1,
        'same_direction_lane_count': 1, 'overtaking': False,
        'conditions_permit_source': 'synthetic_assertion'}, sort_keys=True) + '\n')
    (folder / 'road.xodr').write_text(open_drive() + '\n')
    seal(folder)


def reject(folder, expected):
    try:
        measure(folder)
    except ValueError as error:
        assert expected in str(error), (expected, str(error))
    else:
        raise AssertionError('Damaged source was accepted: ' + expected)


def main():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c102372-window-', dir=output_root) as directory:
        base = Path(directory)
        results = {}
        for label, gap_m, relation in (('above', 165, 'above'), ('below', 140, 'below')):
            folder = base / label
            write_case(folder, gap_m)
            result = measure(folder)
            assert result['duration_s'] == 30 and result['frames'] == 600
            assert result['relation_to_500ft'] == relation
            assert not result['physical_conditions_verified'] and not result['legal_verdict_claimed']
            command = [sys.executable, str(NATIVE / 'measure_delivery_gap.py'), '--source', str(folder)]
            process = subprocess.run(command, text=True, capture_output=True, check=True)
            assert json.loads(process.stdout) == result
            results[label] = {'median_road_gap_m': result['median_road_gap_m'],
                              'source_manifest_sha256': result['source_manifest_sha256']}
            samples = folder / 'native_samples.jsonl'
            original = samples.read_text()
            samples.write_text(original[:-1])
            reject(folder, 'Original source missing or changed')
            samples.write_text(''.join(original.splitlines(keepends=True)[:-1]))
            seal(folder)
            reject(folder, 'Full 600-frame original source required')
            rows = [json.loads(line) for line in original.splitlines()]
            rows[-1]['native_frame'] = 598
            samples.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            seal(folder)
            reject(folder, 'Original 600-frame time join differs at 599')
            rows[-1]['native_frame'] = 599
            rows[-1]['lead']['body_xy_m'] = [[x, -2 + (y + 2) * .1]
                                                  for x, y in rows[-1]['lead']['body_xy_m']]
            samples.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            seal(folder)
            reject(folder, 'Truck below 80-inch width')
            samples.write_text(original)
            seal(folder)
            assert measure(folder) == result
        print(json.dumps({'passed': True, 'scope': 'synthetic 30-second software measurement only',
                          'cases': results, 'negatives_per_case': 4,
                          'physical_observation_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
