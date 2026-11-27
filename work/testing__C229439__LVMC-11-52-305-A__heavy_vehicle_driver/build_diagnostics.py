"""Make tiny source-shaped service parking fixtures; these never establish original fact."""

import hashlib
import json
from pathlib import Path

from service_parking import CASES, SOURCE_FIELDS
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
        scene = {'cell_id': 'C229439', 'actor': 'heavy_vehicle_driver',
                 'vehicle_id': 'synthetic-heavy-v1', 'driver_id': 'synthetic-driver',
                 'worker_id': 'synthetic-worker', 'heavy_vehicle_blueprint': 'vehicle.carlamotors.carlacola',
                 'commercial_vehicle': True, 'street_public': True,
                 'city_jurisdiction': True, 'adjacent_kind': case.adjacent_kind,
                 'school_public': True, 'business_district': False,
                 'mainly_residential': True, 'work_kind': case.work_kind,
                 'work_near': case.work_near, 'length_ft': case.length_ft,
                 'unladen_lb': case.unladen_lb, 'frontage_ft': case.frontage_ft,
                 'posted_permission': case.posted_permission, 'loading': case.loading,
                 'governed_curb_rect_m': [0., 0., 3., 6.],
                 'vehicle_footprint_rect_m': [.2, .2, 2., 4.],
                 'vehicle_center_xy': [1., 1.],
                 'worksite_xy': [4., 1.] if case.work_near else [200., 1.],
                 'parking_route_xy': [[-2., -2.], [1., 1.]],
                 'park_start_frame': 2,
                 'parking_device_text': 'No commercial vehicle parking except as posted',
                 'work_order_id': 'synthetic-work-order',
                 'work_activity_description': 'synthetic service or repair task'}
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
                   'driver_id': scene['driver_id'], 'worker_id': scene['worker_id'],
                   'work_kind': case.work_kind, 'length_ft': case.length_ft,
                   'unladen_lb': case.unladen_lb, 'adjacent_kind': case.adjacent_kind,
                   'frontage_ft': case.frontage_ft,
                   'posted_permission': case.posted_permission,
                   'loading': case.loading,
                   'work_active': case.work_kind != 'none',
                   'worksite_xy': scene['worksite_xy'],
                   'vehicle_center_xy': scene['vehicle_center_xy'],
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
        fixture['files']['original-service-parking.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in rows)
        fixture['files']['camera-frame-map.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in joins)
        fixture['files']['service-parking-context.json'] = json.dumps({
            'format': 'c229439-service-parking-context-v1', 'case_id': case_id,
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
