"""Build nine-frame synthetic source fixtures for selected CPU compatibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parked_lamps import CASES, ROW_SOURCES, SCENE_SOURCES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS 484B.473(2)'
REQUIREMENTS = (
    ('qualifying vehicle and highway', 'qualifying_vehicle_and_highway'),
    ('lawfully parked at nighttime', 'parking_and_nighttime'),
    ('displayed lights depressed or dimmed when cowl or parking lamps are not used',
     'displayed_and_auxiliary_lamps'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    ids = [ASSIGNMENT + '__' + case.name for case in CASES]
    plan['requirement_dispositions'] = [
        {'requirement': name, 'source': LAW, 'status': 'selected_required',
         'case_ids': ids,
         'measurement': 'analysis.py:measure',
         'evidence_or_gap': 'Reviewed original site, lawful-parking, night and actual lamp sources are required.'}
        for name, _ in REQUIREMENTS]
    plan['source_observation_mapping'] = {}
    plan['observations'] = [
        {'name': 'original_vehicle_motion', 'mandatory': True,
         'source': 'source-hashed 20 Hz vehicle identity, body and speed'},
        {'name': 'lamp_state', 'mandatory': True,
         'source': 'source-hashed displayed, cowl and parking lamp readback'},
        {'name': 'camera_pixels', 'mandatory': True,
         'source': 'four synchronized original RGB camera streams'}]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'parked vehicle, highway setting and lamps',
             'interval': 'full 45 s'},
            {'view': 'approach', 'subject': 'vehicle parking route and stationary interval',
             'interval': 'approach through final parked frame'},
            {'view': 'reference_corner',
             'subject': 'curb geometry and displayed cowl or parking lamps',
             'interval': 'parking approach through final lamp observation'},
            {'view': 'driver_reference',
             'subject': 'original lamp visibility and beam aim context',
             'interval': 'full parked interval'}]}
    write(plan_path, plan)
    fixture = json.loads((ROOT / 'runtime/fixtures/example.json').read_text())
    traces = [json.loads(line) for line in fixture['files']['trace.jsonl'].splitlines()]
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        source_root = HERE / 'cases' / case.name / 'diagnostic-sources'
        source_root.mkdir(parents=True, exist_ok=True)
        scene = {'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
                 'qualifying_vehicle': True, 'highway': True,
                 'vehicle_id': 'synthetic-vehicle', 'night': case.night,
                 'lawful_park': case.lawful_park, 'lamp_mode': case.lamp_mode,
                 'auxiliary_lamp': case.auxiliary_lamp,
                 'parking_route_xy': [[0.0, 0.0], [1.0, 0.0]],
                 'curb_distance_m': .2, 'vehicle_width_m': 1.8,
                 'park_start_frame': 0}
        refs = {}
        for name in (*SCENE_SOURCES, 'map_opendrive'):
            path = source_root / (name + '.txt')
            path.write_text('SYNTHETIC SOFTWARE FIXTURE: ' + name + '\n')
            digest = sha(path)
            refs[name] = {'path': path.name, 'sha256': digest,
                          'observation': 'Synthetic software fixture for ' + name,
                          'review_status': 'synthetic'}
            scene['map_opendrive_sha256' if name == 'map_opendrive'
                  else name + '_source_sha256'] = digest
        packet = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
                  'source_kind': 'synthetic_fixture', 'review_status': 'synthetic',
                  'scene': scene, 'source_refs': refs}
        write(source_root / 'reviewed-packet.json', packet)
        rows = []
        for trace in traces:
            row = {'original_frame': trace['frame'], 'time_s': trace['time_s'],
                   'vehicle_id': scene['vehicle_id'], 'night': case.night,
                   'lawful_park': case.lawful_park, 'lamp_mode': case.lamp_mode,
                   'auxiliary_lamp': case.auxiliary_lamp,
                   'speed_mps': trace['speed_mps'],
                   'beam_aim_deg': -2.0 if case.lamp_mode == 'dimmed' else 2.0}
            row.update({name + '_source_sha256': scene[name + '_source_sha256']
                        for name in ROW_SOURCES})
            rows.append(row)
        (source_root / 'original-ticks.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        common_inputs = ['reviewed-packet.json', 'parking_lawfulness.txt',
                         'nighttime.txt', 'displayed_lights.txt', 'beam_aim.txt',
                         'cowl_lamp.txt', 'parking_lamp.txt', 'vehicle_motion.txt',
                         'original-ticks.jsonl']
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'negative': {'remove': ['parking_lawfulness.txt'],
                                 'error_contains': 'Missing required source: parking_lawfulness.txt'},
                    'requirements': [
                        {'disposition_index': index, 'requirement': name,
                         'source': LAW, 'output_key': key, 'method': 'measure',
                         'value_type': 'object', 'kind': 'measured',
                         'inputs': common_inputs}
                        for index, (name, key) in enumerate(REQUIREMENTS)]}
        write(HERE / 'cases' / case.name / 'measurement-contract.json', contract)
        source_names = ['reviewed-packet.json', 'original-ticks.jsonl'] + [
            name + '.txt' for name in (*SCENE_SOURCES, 'map_opendrive')]
        recipe = {'format': 'worker-fixture-recipe',
                  'generator': {'source': 'runtime/fixtures/example.json',
                                'sha256': sha(ROOT / 'runtime/fixtures/example.json')},
                  'sources': [
                      {'path': name,
                       'source': str((source_root / name).relative_to(ROOT)),
                       'sha256': sha(source_root / name)}
                      for name in source_names]}
        write(HERE / 'cases' / case.name / 'fixture-recipe.json', recipe)
    return len(CASES)


if __name__ == '__main__':
    print(build())
