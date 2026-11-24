"""Two 600-frame source-only positives and material saved-source negatives."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from request import CASE, CASES, HERE, sha
from saved import CAMERAS, inspect

ROOT = CASE.parents[1]
SCRATCH = ROOT / '.runtime-work'


def write_rows(path: Path, rows: list[dict]):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def fixture(destination: Path, case: str):
    destination.mkdir()
    shutil.copyfile(HERE / 'drafts' / case / 'config.json', destination / 'config.json')
    requested = [json.loads(line) for line in
                 (HERE / 'drafts' / case / 'requested-tracks.jsonl').read_text().splitlines()]
    mapping = []
    walker = []
    controls = []
    for i, row in enumerate(requested):
        frame = i + 1000
        time = row['time_s']
        mapping.append({'video_frame': i, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        walker.append({'native_frame': frame, 'time_s': time,
                       'footprint_center_xy_m': [row['requested_x_m'], row['requested_y_m']],
                       'source_kind': 'synthetic_native_sample'})
        controls.append({'native_frame': frame, 'time_s': time,
                         'intersection_ids': [101, 102],
                         'official_device_ids': [201, 202], 'operating': [True, True],
                         'source_kind': 'synthetic_native_sample'})
    write_rows(destination / 'frame-map.jsonl', mapping)
    write_rows(destination / 'pedestrian.jsonl', walker)
    write_rows(destination / 'devices.jsonl', controls)
    (destination / 'map-readback.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'intersection_x_m': [0, 100], 'intersection_ids': [101, 102],
        'connected_no_intermediate_intersection': True,
        'roadway_y_bounds_m': [-4, 4], 'crosswalk_marking_x_m': 40}) + '\n')
    for camera in CAMERAS:
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-y', '-f', 'lavfi', '-i', 'color=c=black:s=32x32:r=20',
                        '-frames:v', '600', '-c:v', 'ffv1', '-threads', '1',
                        str(destination / (camera + '.mkv'))],
                       check=True, timeout=120)
    inventory = ('frame-map.jsonl', 'pedestrian.jsonl', 'devices.jsonl',
                 'map-readback.json') + tuple(camera + '.mkv' for camera in CAMERAS)
    (destination / 'capture-manifest.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample',
        'sha256': {name: sha(destination / name) for name in inventory}},
        indent=2) + '\n')


def reject(attempt: Path, label: str, edit, expected: str, rebind: bool = True):
    before = {path.name: path.read_bytes() for path in attempt.iterdir() if path.is_file()}
    try:
        edit()
        if rebind:
            manifest = json.loads((attempt / 'capture-manifest.json').read_text())
            for name in manifest['sha256']:
                if (attempt / name).exists():
                    manifest['sha256'][name] = sha(attempt / name)
            (attempt / 'capture-manifest.json').write_text(json.dumps(manifest) + '\n')
        try:
            inspect(attempt)
        except ValueError as exc:
            if expected not in str(exc):
                raise AssertionError(label + ': wrong rejection: ' + str(exc)) from exc
            return {'mutation': label, 'expected_error': expected}
        raise AssertionError(label + ': mutation accepted')
    finally:
        for name, data in before.items():
            (attempt / name).write_bytes(data)


def change_row(path: Path, index: int, key: str, value):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[index][key] = value
    write_rows(path, rows)


def run():
    positives = []
    negatives = []
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='c109166-saved-') as tmp:
        for case in CASES:
            attempt = Path(tmp) / case
            fixture(attempt, case)
            before = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
            value = inspect(attempt)
            assert {p.name: sha(p) for p in attempt.iterdir() if p.is_file()} == before
            assert value['roadway_entry_frame'] == 259
            assert value['marked_crosswalk_at_entry_in_diagnostic_source'] == (case == 'marked_crosswalk')
            positives.append(value)
            if case == 'marked_crosswalk':
                negatives.append(reject(attempt, 'unbound pedestrian bytes',
                    lambda: change_row(attempt / 'pedestrian.jsonl', 259,
                                       'footprint_center_xy_m', [40, -3]),
                    'Saved source hash differs', rebind=False))
                negatives.append(reject(attempt, 'wrong frame join',
                    lambda: change_row(attempt / 'frame-map.jsonl', 259, 'carla_frame', 9999),
                    'Saved frame identity'))
                negatives.append(reject(attempt, 'disabled device at entry',
                    lambda: change_row(attempt / 'devices.jsonl', 259, 'operating', [True, False]),
                    'Saved official devices not operating'))
                negatives.append(reject(attempt, 'intermediate intersection',
                    lambda: (attempt / 'map-readback.json').write_text(json.dumps({
                        **json.loads((attempt / 'map-readback.json').read_text()),
                        'connected_no_intermediate_intersection': False}) + '\n'),
                    'Saved adjacent-intersection topology differs'))
                negatives.append(reject(attempt, 'missing fourth camera',
                    lambda: (attempt / 'devices.mkv').unlink(),
                    'Saved source hash differs'))
    report = {'format': 'c109166-source-only-saved-proof-v1',
              'positive_cases': positives, 'negative_controls': negatives,
              'source_unchanged': True, 'original_native_observed': False,
              'delivery_ready': False}
    (HERE / 'saved-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    result = run()
    print(json.dumps({'positive': len(result['positive_cases']),
                      'negative': len(result['negative_controls'])}))
