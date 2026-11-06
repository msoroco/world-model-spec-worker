"""Synthetic 240-frame threshold crossings for all three C10316 fallbacks."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from fallback_triggers import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def main():
    original = REPO / '.runtime-work/c10316-crosswalk-synthetic/reference/native_samples.jsonl'
    if not original.is_file():
        raise ValueError('Build the source-bound crosswalk fixture first')
    raw = [json.loads(line) for line in original.read_text().splitlines()]
    if len(raw) != 240:
        raise ValueError('Source crosswalk fixture duration changed')
    root = REPO / '.runtime-work/c10316-fallback-trigger-v1'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    results = {}
    for label in ('baseline', 'spawn', 'tracking', 'visibility', 'wrong_kind'):
        rows = []
        for index, original_row in enumerate(raw):
            row = {'source_kind': 'synthetic_cpu_fixture',
                   'native_frame': 100 + index, 'time_s': round(index / 20, 4),
                   'pedestrian_xy_m': list(original_row['pedestrian_xy_m']),
                   'pedestrian_footprint_xy_m': [list(point) for point in original_row['pedestrian_footprint_xy_m']],
                   'requested_xy_m': list(original_row['pedestrian_xy_m']),
                   'synthetic_camera_annotation': {'approach': True, 'reference_corner': True}}
            if label == 'spawn' and index == 0:
                row['pedestrian_xy_m'][0] += 1.2
                for point in row['pedestrian_footprint_xy_m']:
                    point[0] += 1.2
                row['requested_xy_m'][0] += 1.2
            if label == 'tracking' and 70 <= index < 80:
                row['pedestrian_xy_m'][1] += .25
                for point in row['pedestrian_footprint_xy_m']:
                    point[1] += .25
            if label == 'visibility' and index < 20:
                row['synthetic_camera_annotation']['approach'] = False
            if label == 'wrong_kind':
                row['source_kind'] = 'original_native_capture'
            rows.append(row)
        path = root / (label + '.jsonl')
        put(path, rows)
        if label == 'wrong_kind':
            try:
                measure(path, sha(path))
            except ValueError as exc:
                assert 'provenance-marked' in str(exc)
                results[label] = {'rejected': True, 'error': str(exc)}
            else:
                raise AssertionError('False original-source kind passed')
            continue
        value = measure(path, sha(path))
        expected = {'baseline': (False, False, False), 'spawn': (True, False, False),
                    'tracking': (False, True, False), 'visibility': (False, False, True)}[label]
        assert tuple(value['fallback' + str(i) + '_trigger'] for i in (1, 2, 3)) == expected
        results[label] = value
    changed = root / 'changed_hash.jsonl'
    shutil.copyfile(root / 'baseline.jsonl', changed)
    try:
        measure(changed, '0' * 64)
    except ValueError as exc:
        assert 'Changed fallback observation source' in str(exc)
        results['changed_hash'] = {'rejected': True, 'error': str(exc)}
    else:
        raise AssertionError('Changed source hash passed')
    receipt = {'format': 'c10316-synthetic-fallback-trigger-proof-v1',
        'source_dir': str(root.relative_to(REPO)), 'source_kind': 'synthetic_cpu_fixture',
        'cases': results, 'selected': False, 'original_native_observed': False,
        'original_pixels_observed': False}
    (HERE / 'fallback-trigger-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'synthetic_cases': 4, 'crossing_fallbacks': 3,
                      'changed_hash_rejected': True, 'false_original_kind_rejected': True}))


if __name__ == '__main__':
    main()
