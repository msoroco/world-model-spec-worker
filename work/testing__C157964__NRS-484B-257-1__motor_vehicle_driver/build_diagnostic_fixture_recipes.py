"""Inventory compact, source-sealed diagnostic inputs for the four yield cases.

These fixtures exercise software only. The fake adapter and text PPM pixels do
not represent reviewed roadway evidence or original Native camera capture.
"""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from native_capture import VIEWS, capture
from tests.test_native_capture import FakeAdapter, fixture
from yield_view import CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PIXEL = ('P3\n2 2\n255\n'
         '30 60 90 30 60 90\n'
         '30 60 90 30 60 90\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def build_one(case, scratch):
    source = scratch / 'reviewed-source'
    source.mkdir()
    packet = fixture(source, case)
    attempt = scratch / 'captured-attempt'
    capture(FakeAdapter(case), packet, source, attempt, case, diagnostic=True)
    destination = ROOT / 'diagnostic-sources' / case.case_id
    assert not destination.exists(), 'Diagnostic fixture already exists: ' + case.case_id
    original = destination / 'original-attempt'
    original.mkdir(parents=True)
    for name in ('reviewed-site-packet.json', 'reviewed-source-index.json',
                 'measurement.json'):
        shutil.copyfile(attempt / name, original / name)
    shutil.copytree(attempt / 'reviewed-sources', original / 'reviewed-sources')
    rows = json.loads((attempt / 'rows.json').read_text())
    write_json(original / 'rows.json', rows)
    pixel = original / 'camera.ppm'
    pixel.write_text(PIXEL)
    camera_index = json.loads((attempt / 'camera-index.json').read_text())
    for view in VIEWS:
        for entry in camera_index[view]:
            entry['path'] = 'camera.ppm'
            entry['sha256'] = digest(pixel)
    write_json(original / 'camera-index.json', camera_index)
    seal = json.loads((attempt / 'seal.json').read_text())
    seal['rows_sha256'] = digest(original / 'rows.json')
    seal['camera_index_sha256'] = digest(original / 'camera-index.json')
    write_json(original / 'seal.json', seal)
    with (destination / 'trace.jsonl').open('w') as trace, \
            (destination / 'video_frames.jsonl').open('w') as mapping:
        for index, row in enumerate(rows):
            frame = row['original_frame']
            time_s = row['time_s']
            trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                                    'position': {'x': 0, 'y': 0, 'z': 0},
                                    'position_m': [0, 0, 0],
                                    'heading_deg': 0,
                                    'speed_mps': row['ego_speed_mps'],
                                    'speed_mph': row['ego_speed_mps'] / .44704,
                                    'velocity_mps': [row['ego_speed_mps'], 0, 0],
                                    'control': {'throttle': 0, 'steer': 0,
                                                'brake': 0, 'hand_brake': False,
                                                'reverse': False,
                                                'manual_gear_shift': False,
                                                'gear': 0}}, sort_keys=True) + '\n')
            mapping.write(json.dumps({'video_frame': index,
                                      'carla_frame': frame,
                                      'native_frame': frame,
                                      'time_s': time_s}, sort_keys=True) + '\n')
    spec = {'files': {}, 'graphs': [],
            'videos': [{'path': view + '.mkv', 'frames': 900,
                        'width': 1920 if view == 'overview' else 1280,
                        'height': 1080 if view == 'overview' else 720,
                        'fps': 20, 'color': 'black'} for view in VIEWS]}
    spec_path = ROOT / ('diagnostic-fixture-spec-' + case.case_id + '.json')
    write_json(spec_path, spec)
    entries = []
    for file in sorted(destination.rglob('*')):
        if file.is_file():
            relative = file.relative_to(destination).as_posix()
            entries.append({'path': relative,
                            'source': file.relative_to(REPO).as_posix(),
                            'sha256': digest(file)})
            assert file.stat().st_size <= 2 * 1024 * 1024, relative
    recipe = {'format': 'worker-fixture-recipe', 'sources': entries,
              'generator': {'source': spec_path.relative_to(REPO).as_posix(),
                            'sha256': digest(spec_path)}}
    recipe_path = ROOT / ('diagnostic-fixture-recipe-' + case.case_id + '.json')
    write_json(recipe_path, recipe)
    return {'case_id': case.case_id, 'recipe': recipe_path.name,
            'source_count': len(entries),
            'site_packet_sha256': digest(original / 'reviewed-site-packet.json')}


def main():
    private = REPO / '.runtime-work'
    private.mkdir(exist_ok=True)
    outcomes = []
    for case in CASES:
        with tempfile.TemporaryDirectory(dir=private,
                                         prefix='c157964-fixture-') as temporary:
            outcomes.append(build_one(case, Path(temporary)))
    print(json.dumps(outcomes, indent=2))


if __name__ == '__main__':
    main()
