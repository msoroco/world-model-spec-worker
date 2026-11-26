"""Make tiny source-shaped City-space fixtures; these never establish original fact."""

import hashlib
import json
from pathlib import Path

from city_space import CASES, SOURCE_FIELDS
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    example = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    frames = [json.loads(line) for line in example['files']['video_frames.jsonl'].splitlines()]
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        scene = {'cell_id': 'C229439', 'actor': 'vehicle_parker',
                 'vehicle_id': 'synthetic-parked-v1',
                 'parking_person_id': 'synthetic-person-p1',
                 'city_location_kind': 'city_street',
                 'city_vehicle': case.city_vehicle,
                 'designated': case.designated, 'posted': case.posted,
                 'inside_space': case.inside_space,
                 'governed_space_rect_m': [0., 0., 3., 6.],
                 'vehicle_footprint_rect_m': [.2, .2, 2., 4.] if case.inside_space
                 else [7., 7., 9., 9.],
                 'parking_route_xy': [[-2., -2.], [1., 1.]],
                 'park_start_frame': 2,
                 'official_device_text': 'City vehicles only',
                 'city_vehicle_authority_ref': 'synthetic authority record',
                 'council_designation_ref': 'synthetic Council record'}
        for field in SOURCE_FIELDS:
            scene[field + '_source_sha256'] = hashlib.sha256((
                'CPU diagnostic ' + case_id + ' ' + field).encode()).hexdigest()
        fixture = {'files': dict(example['files']), 'graphs': example['graphs'],
                   'videos': example['videos']}
        rows = []
        joins = []
        for index, frame in enumerate(frames):
            original = frame['carla_frame']
            row = {'original_frame': original, 'time_s': frame['time_s'],
                   'vehicle_id': scene['vehicle_id'],
                   'parking_person_id': scene['parking_person_id'],
                   'official_device_text': scene['official_device_text'],
                   'city_vehicle': case.city_vehicle,
                   'designated': case.designated, 'posted': case.posted,
                   'vehicle_center_xy': [1., 1.] if case.inside_space else [8., 8.],
                   'vehicle_footprint_rect_m': scene['vehicle_footprint_rect_m'],
                   'speed_mps': 1. if index < scene['park_start_frame'] else 0.}
            for field in SOURCE_FIELDS:
                row[field + '_source_sha256'] = scene[field + '_source_sha256']
            rows.append(row)
            joins.append({'frame_index': index, 'native_frame': original,
                          'time_s': frame['time_s'],
                          'camera_frames': {name: original for name in
                                            ('overview', 'approach', 'reference_corner',
                                             'driver_reference')}})
        fixture['files']['original-city-space.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in rows)
        fixture['files']['camera-frame-map.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in joins)
        fixture['files']['city-space-context.json'] = json.dumps({
            'format': 'c229439-city-space-context-v1', 'case_id': case_id,
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
