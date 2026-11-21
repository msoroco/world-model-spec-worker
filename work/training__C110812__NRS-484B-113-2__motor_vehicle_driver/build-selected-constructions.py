"""Build 42-second exact-case candidates while retaining the diagnostic drafts."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
spec = importlib.util.spec_from_file_location('c110812_cameras', HERE / 'native/cameras.py')
cameras = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cameras)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_replace(source, old, new):
    if old not in source:
        raise ValueError('Expected draft duration marker absent: ' + old)
    return source.replace(old, new)


def build(suffix, candidate):
    source = HERE / 'draft-candidates' / suffix / candidate / 'construction.json'
    bundle = copy.deepcopy(json.loads(source.read_text()))
    for item in bundle['files']:
        path, content = item['path'], item['content']
        if path == 'runner.py':
            content = exact_replace(content, 'config["duration_s"] != 24', 'config["duration_s"] != 42')
        elif path == 'measure.py':
            content = exact_replace(content, "len(rows)!=480:raise ValueError('Exact 480-frame saved path required')",
                                    "len(rows)!=840:raise ValueError('Exact 840-frame saved path required')")
        elif path == 'finalize.py':
            content = exact_replace(content, 'original 24 s / 480 frame attempt',
                                    'original 42 s / 840 frame attempt')
        elif path == 'config.json':
            config = json.loads(content)
            config['duration_s'] = 42
            config['engineering_knobs']['duration_s'] = 42
            config['supported_case_ids'] = [HERE.name + '__false', HERE.name + '__true']
            config['status'] = 'cpu_delivery_preparation'
            for channel in config['recording_description']['channels']:
                channel['time_window'] = '42 s / 840 joined frames'
            plans = {plan['name']: plan for plan in cameras.camera_plan(candidate)}
            for camera in config['cameras']:
                plan = plans[camera['name']]
                camera.update({key: plan[key] for key in ('fov_deg', 'xyz_m', 'pitch_deg')})
                camera['pose_strategy'] = 'fixed surveyed intersection and corner world camera'
            content = json.dumps(config, indent=2) + '\n'
        item['content'] = content
    for channel in bundle['recording_description']['channels']:
        channel['time_window'] = '42 s / 840 joined frames'
    bundle['static_checks'] = [text.replace('480-frame', '840-frame') for text in bundle['static_checks']]
    bundle['termination_rules'] = [text.replace('480 original', '840 original') for text in bundle['termination_rules']]
    bundle['status'] = 'selected_cpu_proof_pending'
    destination = HERE / 'cases' / suffix / candidate / 'construction.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, indent=2) + '\n')
    return destination


manifest = copy.deepcopy(draft)
manifest['format'] = 'worker-selected-proof-manifest-v1'
manifest['status'] = 'selected_cpu_proof_pending'
for entry in manifest['cases']:
    suffix = 'condition_a' if entry['case_id'].endswith('__false') else 'condition_b'
    entry['kind'] = 'delivery'
    primary = build(suffix, 'primary')
    entry['construction'] = str(primary.relative_to(HERE))
    entry['construction_sha256'] = sha(primary)
    for candidate in entry['candidates']:
        path = build(suffix, candidate['id'])
        candidate['construction'] = str(path.relative_to(HERE))
        candidate['construction_sha256'] = sha(path)

(HERE / 'selected-proof-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
root_bundle = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
for item in root_bundle['files']:
    target = HERE / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(item['content'])
(HERE / 'construction.json').write_text(json.dumps(root_bundle, indent=2) + '\n')
print(json.dumps({'cases': len(manifest['cases']), 'candidates': 8,
                  'duration_s': 42, 'frames': 840, 'manifest_sha256': sha(HERE / 'selected-proof-manifest.json')}))
