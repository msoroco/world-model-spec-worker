"""Materialize the reviewed three-case Native root package from selected sources."""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


manifest = read(HERE / 'execution-manifest.json')
source = read(HERE / manifest['cases'][0]['construction'])
construction = json.loads(json.dumps(source))
cases = [item['case_id'] for item in manifest['cases']]
description = construction['recording_description']
for name, unit, method in (
    ('kin.speed', 'mph', 'maximum and framewise speed from post-tick Native velocity'),
    ('kin.velocity', 'm/s', 'three-axis post-tick Native velocity vector'),
    ('ru.subject', 'identifier', 'Native vehicle actor identity across all frames'),
):
    description['channels'].append({
        'name': name, 'unit': unit, 'method': method,
        'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
        'reference_frame': 'surveyed roundabout arc and exit',
        'uncertainty': '50 ms sampling; original Native review pending',
    })
for item in construction['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['supported_case_ids'] = cases
        config['status'] = 'cpu_prepared_physical_capture_pending'
        config['recording_description'] = description
        item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
    path = HERE / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item['content'])
construction['status'] = 'cpu_prepared_physical_capture_pending'
write(HERE / 'construction.json', construction)

plan_path = HERE / 'case-plan.json'
plan = read(plan_path)
plan['camera_plan'] = {
    'profile': 'overview1080-capability',
    'duration_s': 30,
    'composition': 'synchronized_four_view_primary',
    'coverage': [
        {'view': 'overview', 'subject': 'motor vehicle, roundabout arc and exit',
         'interval': 'full 30 s'},
        {'view': 'approach', 'subject': 'arc entry and subject approach',
         'interval': 'full 30 s'},
        {'view': 'reference_corner', 'subject': 'exit tangent and lane context',
         'interval': 'full 30 s'},
        {'view': 'driver_reference', 'subject': 'vehicle body and lane trajectory',
         'interval': 'full 30 s'},
    ],
}
for term, item in plan['source_observation_mapping'].items():
    item['evidence'] = item.get('measurement', 'original saved source channel')
    item['channels'] = ['original_vehicle_velocity_position']
plan['requirement_dispositions'][0]['evidence_or_gap'] = (
    'Three selected below/at/above source-hashed CPU diagnostic cases and shared '
    'fallbacks passed current runtime construction and saved processing; original '
    'Native speed, arc/exit traversal and pixels remain later GPU checks.')
write(plan_path, plan)
print(json.dumps({'root_files': [item['path'] for item in construction['files']],
                  'supported_cases': cases}))
