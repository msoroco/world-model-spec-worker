"""Assemble aggregate preparation contract from the exact selected bundle."""
import copy
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
plan_path = folder / 'case-plan.json'
plan = json.loads(plan_path.read_text())
base = json.loads((folder / 'cases/park_effective/construction.json').read_text())
config = json.loads(next(item['content'] for item in base['files'] if item['path'] == 'config.json'))
config['supported_case_ids'] = [case['case_id'] for case in plan['cases']]
config['cameras'] = [
    {'name': 'overview', 'width': 1920, 'height': 1080,
     'pose_strategy': 'reviewed overhead site and governed footprint', 'fov_deg': 90},
    {'name': 'approach', 'width': 1280, 'height': 720,
     'pose_strategy': 'reviewed approach and device legibility', 'fov_deg': 90},
    {'name': 'reference_corner', 'width': 1280, 'height': 720,
     'pose_strategy': 'reviewed device, curb and full body relation', 'fov_deg': 90},
    {'name': 'driver_reference', 'width': 1280, 'height': 720,
     'pose_strategy': 'reviewed original driver reference', 'fov_deg': 90},
]
(folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
root = copy.deepcopy(base)
root.pop('case_id', None)
root['measurement_plan'] = [
    'original 900 frame 20 Hz actor activity and full body history',
    'source-sealed device instruction, authority and effective interval',
    'source-observed exception history',
    'four synchronized original camera streams and capture seal',
]
root['static_checks'] = [
    'exact identity and original source hashes',
    'four-view 20 Hz 45 second capture profile',
    'no physical or legal acceptance from synthetic diagnostic fixtures',
]
root['termination_rules'] = [
    '900 original world frames or explicit failed attempt; never truncate as success',
    'restore CARLA world and owned actors before capture seal',
]
root['mechanisms'] = [
    'per-case pinned runtime materialization from selected execution manifest',
    'source-gated Native CARLA adapter, original observer and four camera writer',
    'saved-only analysis of original media and source-sealed rows',
]
for item in root['files']:
    if item['path'] == 'config.json':
        item.pop('source', None)
        item['content'] = (folder / 'config.json').read_text()
(folder / 'construction.json').write_text(json.dumps(root, indent=2) + '\n')
plan['camera_plan'] = {
    'profile': 'overview1080-capability', 'duration_s': 45,
    'composition': 'synchronized_four_view_primary',
    'coverage': [
        {'view': camera['name'], 'subject': camera['pose_strategy'], 'interval': 'all 900 original ticks'}
        for camera in config['cameras']
    ],
}
plan['source_observation_mapping'] = {}
plan_path.write_text(json.dumps(plan, indent=2) + '\n')
