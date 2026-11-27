"""Generate textual fire-entrance compatibility sources for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_station_scene import ASSIGNMENT, CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n',
                    encoding='utf-8')


def scene(case):
    # These authored values exercise software joins only; no map status is claimed.
    y = -2.0 if case.side == 'opposite' else 2.0
    entrance_y = 2.0
    lateral = abs(y - entrance_y)
    distance_m = case.distance_ft * .3048
    x = (distance_m**2 - lateral**2)**.5
    data = {
        'case_id': case.case_id, 'law_id': 'NRS-484B-450-1j',
        'cell_id': 'C229925', 'actor': 'vehicle_stopping_person',
        'vehicle_class': 'vehicle', 'stopping_person_id': 'synthetic-person',
        'side_request': case.side, 'activity_request': case.activity,
        'nominal_entrance_distance_ft': case.distance_ft,
        'circumstance_request': case.circumstance,
        'entrance_start_xy': [0.0, entrance_y],
        'entrance_end_xy': [1.0, entrance_y],
        'road_origin_xy': [0.0, 0.0], 'road_forward_xy': [1.0, 0.0],
        'vehicle_start_xy': [x+12.0, y], 'vehicle_target_xy': [x+1.0, y],
        'station_is_fire': case.circumstance != 'non_fire_station',
        'highway_public_use': case.circumstance != 'private_road',
        'highway_dedicated': True,
        'vehicle_blueprint_id': 'vehicle.synthetic',
        'entrance_markers': [
            {'blueprint_id': 'static.synthetic', 'xy': [0.0, entrance_y]},
            {'blueprint_id': 'static.synthetic', 'xy': [1.0, entrance_y]}],
        'authority_record_id': 'synthetic-authority',
        'conflicting_vehicle_start_xy': [x-10, y],
        'conflicting_vehicle_target_xy': [x+20, y],
        'conflicting_vehicle_blueprint_id': 'vehicle.synthetic',
        'map_sha256': 'a'*64}
    for key in ('station_identity', 'entrance_boundary', 'highway_boundary',
                'highway_dedication', 'public_vehicular_use', 'entrance_side',
                'stopping_person', 'halt_purpose', 'traffic_conflict',
                'law_direction', 'police_direction', 'official_device_direction'):
        data[key+'_source'] = 'synthetic:' + key
    return data


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text(
        encoding='utf-8'))
    mapping = [json.loads(line) for line in
               base['files']['video_frames.jsonl'].splitlines()]
    for case in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl',
                          'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        data = scene(case)
        x, y = data['vehicle_target_xy']
        vertices = [[x+dx, y+dy, z] for dx in (-.8, .8)
                    for dy in (-.4, .4) for z in (0.0, 1.5)]
        history = []
        for row in mapping:
            history.append({
                'frame': row['carla_frame'], 'time_s': row['time_s'],
                'vehicle_id': 'synthetic-vehicle',
                'vehicle_vertices': vertices,
                'speed_mps': 0.0, 'control_state': case.activity,
                'traffic_vehicle_id': ('synthetic-conflict' if
                                       case.circumstance == 'traffic_conflict' else None),
                'traffic_speed_mps': (3.0 if
                                      case.circumstance == 'traffic_conflict' else None),
                'camera_frame': row['carla_frame']})
        spec['files']['fire-entrance-context.json'] = json.dumps(data) + '\n'
        spec['files']['fire-entrance-trace.jsonl'] = ''.join(
            json.dumps(row) + '\n' for row in history)
        spec['files']['fire-source-receipt.json'] = json.dumps({
            'assignment_id': ASSIGNMENT, 'case_id': case.case_id,
            'source_kind': 'synthetic_diagnostic_fixture',
            'diagnostic_fixture': True, 'frame_count': len(history),
            'fps': 20}) + '\n'
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False,
            'case_id': case.case_id}) + '\n'
        spec['files']['carla_recorder.log'] = 'synthetic diagnostic recorder placeholder\n'
        source = ROOT / ('diagnostic-' + case.name + '.json')
        write(source, spec)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        source_name = str(source.relative_to(REPO))
        recipe = {
            'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json',
                         'source': source_name, 'sha256': checksum}],
            'generator': {'source': source_name, 'sha256': checksum}}
        write(ROOT / ('diagnostic-' + case.name + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
