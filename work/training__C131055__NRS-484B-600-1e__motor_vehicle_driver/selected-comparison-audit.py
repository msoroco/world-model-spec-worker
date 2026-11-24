"""Verify exact selected source binding and isolated synthetic speed difference."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MPH = 2.2369362921


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest = read(HERE / 'execution-manifest.json')
    require(manifest.get('assignment_id') == HERE.name, 'Wrong assignment')
    rows = {}
    source_hashes = {}
    construction_hashes = {}
    for name, number in (('below', 1), ('above', 2)):
        case = HERE.name + f'__controlled_{number}'
        entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
        require(entry is not None and entry.get('kind') == 'delivery', 'Unselected comparison case')
        construction = HERE / entry['construction']
        require(sha(construction) == entry['construction_sha256'], 'Selected construction changed')
        construction_hashes[name] = sha(construction)
        recipe = read(HERE.parents[1] / entry['fixture_recipe'])
        source = next((item for item in recipe['sources']
                       if item['path'] == 'roundabout-speed-history.jsonl'), None)
        require(source is not None, 'Missing source-hashed speed history')
        source_path = HERE.parents[1] / source['source']
        require(sha(source_path) == source['sha256'], 'Selected source hash changed')
        source_hashes[name] = source['sha256']
        rows[name] = [json.loads(line) for line in source_path.read_text().splitlines()]
        require(len(rows[name]) == 600, 'Selected source requires 600 frames')
    a, b = rows['below'], rows['above']
    fixed = ('video_frame', 'native_frame', 'time_s', 'subject_id',
             'position_xyz_m', 'road_id', 'lane_id')
    differences = []
    for i, (left, right) in enumerate(zip(a, b)):
        for key in fixed:
            require(left[key] == right[key], 'Fixed comparison source differs: ' + key)
        require(left['video_frame'] == i and abs(left['time_s'] - i / 20) < 1e-6,
                'Frame/time source join differs')
        require(left['road_id'] == (1 if i < 500 else 2) and left['lane_id'] == -2,
                'Roundabout arc/exit lane source differs')
        if left['velocity_xyz_mps'] != right['velocity_xyz_mps']:
            differences.append(i)
    require(differences == list(range(500, 600)), 'Speed contrast window differs')
    require(all(row['velocity_xyz_mps'][0] * MPH < 80 for row in a) and
            all(row['velocity_xyz_mps'][0] * MPH > 80 for row in b[500:]),
            'Synthetic speed boundary differs')
    return {'format': 'worker-selected-comparison-diagnostic', 'passed': True,
            'selected': True, 'physical_completion': False,
            'construction_sha256': construction_hashes,
            'source_sha256': source_hashes,
            'fixed_conditions_verified': list(fixed),
            'deliberate_difference_frames': [500, 599],
            'deliberate_difference': 'synthetic 29 versus 38 m/s on exit',
            'above_80_mph_is_synthetic': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior comparison receipt')
    args.output.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
