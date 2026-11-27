"""Build small source-shaped diagnostics; no original physical fact is claimed."""

import hashlib
import json
from pathlib import Path

from red_curb import CASES
from source_packet import ASSIGNMENT, CAMERAS, SOURCE_FIELDS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    example = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    frames = [json.loads(line) for line in example['files']['video_frames.jsonl'].splitlines()]
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        scene = {'cell_id': 'C229452', 'actor': 'motor_vehicle_driver',
                 'municipal_jurisdiction': True, 'red_curb_paint': True,
                 'curb_segment_id': 'synthetic-red-edge',
                 'vehicle_kind': case.vehicle_kind, 'sign': case.sign,
                 'activity': case.activity, 'purpose': case.purpose,
                 'mail_dropbox_adjacent': case.mail_adjacent,
                 'parking_route_xy': [[-4., 0.], [0., 0.]],
                 'traffic_conflict': None, 'police_direction': None,
                 'device_direction': None}
        for field in SOURCE_FIELDS:
            scene[field + '_source_sha256'] = hashlib.sha256((
                'CPU diagnostic ' + case_id + ' ' + field).encode()).hexdigest()
        fixture = {'files': dict(example['files']), 'graphs': example['graphs'],
                   'videos': example['videos']}
        events = []
        for index, t in ((0, 0), (len(frames) - 1, case.duration_s)):
            row = {'vehicle_id': 'synthetic-ego',
                   'original_frame': frames[index]['carla_frame'],
                   'original_time_s': t, 'vehicle_speed_mps': 0,
                   'halted': True, 'activity': case.activity,
                   'purpose': case.purpose, 'attended': False,
                   'engine_running': False,
                   'red_curb_source_sha256': scene['red_curb_source_sha256']}
            for field in ('event', 'vehicle_motion', 'curb_position', 'activity',
                          'attendance', 'engine', 'sign', 'purpose'):
                row[field + '_source_sha256'] = hashlib.sha256((
                    'CPU diagnostic event ' + case_id + ' ' + field).encode()).hexdigest()
            events.append(row)
        joins = [{'frame_index': index, 'native_frame': frame['carla_frame'],
                  'time_s': frame['time_s'],
                  'camera_frames': {name: frame['carla_frame'] for name in CAMERAS}}
                 for index, frame in enumerate(frames)]
        fixture['files']['original-red-curb-events.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in events)
        fixture['files']['camera-frame-map.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in joins)
        fixture['files']['red-curb-context.json'] = json.dumps({
            'format': 'c229452-red-curb-context-v1', 'case_id': case_id,
            'scene': scene, 'source_kind': 'synthetic_diagnostic_fixture'},
            sort_keys=True) + '\n'
        fixture['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False, 'case_id': case_id}) + '\n'
        target = ROOT / 'diagnostics' / case.name
        target.mkdir(parents=True, exist_ok=True)
        spec = target / 'diagnostic.json'
        spec.write_text(json.dumps(fixture, separators=(',', ':')) + '\n')
        source = str(spec.relative_to(REPO))
        digest = sha(spec)
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': source, 'sha256': digest}],
                  'generator': {'source': source, 'sha256': digest}}
        (target / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
        print(case.name, spec.stat().st_size)


if __name__ == '__main__':
    build()
