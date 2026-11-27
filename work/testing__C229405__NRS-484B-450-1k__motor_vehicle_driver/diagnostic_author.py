"""Generate seven source-inventoried synthetic compatibility specifications."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from excavation_park import CASES, available_passage_width

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n',
                    encoding='utf-8')


def scene(item):
    data = {
        'cell_id': 'C229405', 'actor': 'motor_vehicle_driver',
        'driver_present': True, 'motor_vehicle': True,
        'highway_public_access': True, 'highway_dedicated': True,
        'excavation_kind': 'highway_excavation',
        'relation': item.relation, 'halt_activity': item.activity,
        'passage': item.passage, 'exception': item.exception,
        'road_centerline_y_m': 0,
        'vehicle_target_xy': [1, 2], 'traffic_start_xy': [-8, 0],
        'excavation_rect_m': [0, 0.2, 2, 1.2],
        'target_body_rect_m': [0, 2, 2, 3],
        'traffic_lane_span_y_m': [-2.3, 0],
        'planned_passage_width_m': 2.3,
        'parking_route_xy': [[-8, 2], [1, 2]],
        'traffic_route_xy': [[-8, 0], [15, 0]],
        'conflicting_traffic_id': 'synthetic-conflict',
        'authority_record_id': 'synthetic-authority',
        'highway_status': 'synthetic', 'driver_identity': 'synthetic',
        'motor_vehicle_class': 'synthetic',
        'excavation_status': 'synthetic',
        'traffic_conflict_necessity': 'unresolved',
        'law_compliance': 'unresolved',
        'officer_direction': 'unresolved',
        'official_device_direction': 'unresolved'}
    if item.relation == 'opposite':
        data.update(target_body_rect_m=[0, -3, 2, -2],
                    vehicle_target_xy=[1, -2],
                    parking_route_xy=[[-8, -2], [1, -2]],
                    traffic_lane_span_y_m=[1.2, 3.5],
                    planned_passage_width_m=2.3)
    if item.passage == 'open':
        data.update(traffic_lane_span_y_m=[-3.5, 0],
                    planned_passage_width_m=3.5)
    for name in ('highway', 'vehicle', 'driver', 'excavation', 'parking_route',
                 'traffic_route', 'traffic_actor', 'halt_activity', 'exception'):
        data[name + '_source_sha256'] = 'synthetic-' + name
    return data


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for item in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        data = scene(item)
        width = available_passage_width(data['traffic_lane_span_y_m'],
                                        data['target_body_rect_m'],
                                        data['excavation_rect_m'])
        history = []
        for row in mapping:
            entry = {
                'original_frame': row['carla_frame'], 'time_s': row['time_s'],
                'vehicle_id': 'synthetic-ego', 'traffic_id': 'synthetic-traffic',
                'relation': item.relation, 'halt_activity': item.activity,
                'exception': item.exception,
                'vehicle_body_rect_m': data['target_body_rect_m'],
                'excavation_rect_m': data['excavation_rect_m'],
                'passage_width_m': width,
                'traffic_speed_mps': 4.0, 'vehicle_speed_mps': 0.0,
                'excavation_source_sha256': data['excavation_source_sha256']}
            for name in ('frame', 'vehicle_motion', 'vehicle_body', 'passage',
                         'traffic_motion', 'activity', 'exception'):
                entry[name + '_source_sha256'] = 'synthetic-' + name
            history.append(entry)
        spec['files']['excavation-site.json'] = json.dumps({'scene': data}) + '\n'
        spec['files']['excavation-history.jsonl'] = ''.join(
            json.dumps(row) + '\n' for row in history)
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False,
            'case_id': ROOT.name + '__' + item.case_id}) + '\n'
        spec['files']['carla_recorder.log'] = 'synthetic diagnostic recorder placeholder\n'
        source = ROOT / ('diagnostic-' + item.case_id + '.json')
        write(source, spec)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        source_name = str(source.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': source_name, 'sha256': checksum}],
                  'generator': {'source': source_name, 'sha256': checksum}}
        write(ROOT / ('diagnostic-' + item.case_id + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
