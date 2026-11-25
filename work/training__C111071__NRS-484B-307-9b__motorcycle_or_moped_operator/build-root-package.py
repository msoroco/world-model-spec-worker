"""Materialize the canonical root entrypoint from the proved first case."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
first = manifest['cases'][0]
selected = json.loads((ROOT / first['construction']).read_text())
case_ids = [entry['case_id'] for entry in manifest['cases']]
files = []
for item in selected['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['supported_case_ids'] = case_ids
        for camera, strategy in zip(config['cameras'], (
                'fixed overhead junction view', 'fixed stop approach view',
                'fixed governing signal and crosswalk corner view',
                'motorcycle driver reference view')):
            camera['pose_strategy'] = strategy
            camera['fov_deg'] = 90
        content = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
    else:
        content = item['content']
    path = ROOT / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    files.append({'path': item['path'], 'content': content})

construction = {
    'case_id': first['case_id'],
    'law_id': selected['law_id'],
    'cell_id': selected['cell_id'],
    'actor': selected['actor'],
    'entrypoint': 'runner.py',
    'files': files,
    'recording_description': selected['recording_description'],
    'mechanisms': {
        'source': 'selected first-case Native runner and source bridge',
        'scope': 'four exact straight-cell cases, each with separately hashed selected bundles',
        'physical_completion': 'requires original CARLA attempt and independent source review',
    },
    'termination_rules': ['600 synchronous frames at 20 Hz', 'fail closed on missing source or camera join'],
    'status': 'draft',
    'measurement_plan': ['source-bound body stop, signal cycles, detector trace and lawful conflict review'],
    'static_checks': ['selected primary offline and compatibility receipts', 'original source bridge CPU negatives'],
}
(ROOT / 'construction.json').write_text(json.dumps(construction, indent=2, ensure_ascii=False) + '\n')

plan_path = ROOT / 'case-plan.json'
plan = json.loads(plan_path.read_text())
plan['camera_plan'] = {
    'profile': 'overview1080-capability',
    'duration_s': 30,
    'composition': 'synchronized_four_view_primary',
    'coverage': [
        {'view': 'overview', 'subject': 'motorcycle, signal, crossing pedestrians and intersection traffic', 'interval': '0-30 s'},
        {'view': 'approach', 'subject': 'full-body stop reference and detector footprint', 'interval': '0-30 s'},
        {'view': 'reference_corner', 'subject': 'governing red/left-arrow face and adjacent crosswalk', 'interval': '0-30 s'},
        {'view': 'driver_reference', 'subject': 'motorcycle driver perspective and conflict participants', 'interval': '0-30 s'},
    ],
}
plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'root_files': len(files), 'cases': len(case_ids), 'camera_profile': plan['camera_plan']['profile']}))
