"""Materialize the reviewed root bundle from the exact straight-reverse primary."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
bundle = json.loads((HERE / 'draft-candidates/condition_a/primary/construction.json').read_text())
module_path = HERE / 'native/cameras.py'
spec = importlib.util.spec_from_file_location('c110812_cameras', module_path)
camera_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera_module)
plans = {camera['name']: camera for camera in camera_module.camera_plan('primary')}
config_file = next(item for item in bundle['files'] if item['path'] == 'config.json')
config = json.loads(config_file['content'])
config['supported_case_ids'] = [HERE.name + '__' + suffix for suffix in ('false', 'true')]
config['duration_s'] = 42
config['status'] = 'cpu_delivery_preparation'
for channel in config['recording_description']['channels']:
    channel['time_window'] = '42 s / 840 joined frames'
for camera in config['cameras']:
    plan = plans[camera['name']]
    for key in ('fov_deg', 'xyz_m', 'pitch_deg'):
        camera[key] = plan[key]
    camera['pose_strategy'] = 'fixed surveyed intersection and corner world camera'
config_file['content'] = json.dumps(config, indent=2) + '\n'
for item in bundle['files']:
    path = HERE / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item['content'])
(HERE / 'construction.json').write_text(json.dumps(bundle, indent=2) + '\n')
print(json.dumps({'root_files': len(bundle['files']),
                  'supported_case_ids': config['supported_case_ids']}))
