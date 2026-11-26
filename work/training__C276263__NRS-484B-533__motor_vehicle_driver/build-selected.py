"""Bind five exact Native cases and curb-focused camera-position fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ('reference', 'contrast', 'engine_on', 'brake_unset', 'wheel_straight')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    draft = json.loads((HERE / 'diagnostic-execution-manifest.json').read_text())
    draft['format'] = 'worker-execution-manifest'
    draft['status'] = 'selected_cpu_preparation'
    for entry in draft['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if suffix not in SUFFIXES:
            raise ValueError('Unexpected duty case')
        source = json.loads((HERE / entry['construction']).read_text())
        files = {item['path']: item for item in source['files']}
        files['runner.py']['content'] = (HERE / 'native' / 'runner.py').read_text()
        config = json.loads(files['config.json']['content'])
        config['cameras'] = [
            {'name': name, 'width': 1920 if name == 'overview' else 1280,
             'height': 1080 if name == 'overview' else 720,
             'pose_strategy': 'surveyed right-curb stationary body and driver-side coverage',
             'fov_deg': 85}
            for name in CAMERAS]
        config['status'] = 'selected_cpu_preparation'
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        source['files'] = list(files.values())
        source['status'] = 'selected_cpu_preparation'
        primary = HERE / 'selected-grade' / suffix / 'primary' / 'construction.json'
        write(primary, source)
        entry['construction'] = str(primary.relative_to(HERE))
        entry['construction_sha256'] = sha(primary)
        fallback = json.loads(primary.read_text())
        for item in fallback['files']:
            if item['path'] == 'capture.py':
                old = "('reference_corner', 4, -5, 2, -12)"
                new = "('reference_corner', 3, -6, 3, -16)"
                if old not in item['content']:
                    raise ValueError('Camera position knob absent')
                item['content'] = item['content'].replace(old, new)
            elif item['path'] == 'config.json':
                cfg = json.loads(item['content'])
                cfg['candidate_id'] = 'fallback1'
                item['content'] = json.dumps(cfg, indent=2) + '\n'
        alternate = HERE / 'selected-grade' / suffix / 'fallback1' / 'construction.json'
        write(alternate, fallback)
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original curb-side pixels may not resolve both front wheels and right curb together; local camera coverage needs review'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': str(alternate.relative_to(HERE)),
            'construction_sha256': sha(alternate),
            'trigger': {'source': 'original reference_corner.mkv and video_frames.jsonl',
                        'metric': 'simultaneous curb and two-front-wheel visibility over the unattended interval',
                        'failure_condition': 'either front wheel or curb is obscured in original decoded frames after source completeness checks'},
            'changed_knobs': ['reference_corner camera mount from (4,-5,2,-12) to (3,-6,3,-16) meters/degrees; all cases and observations fixed']}]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
    write(HERE / 'execution-manifest.json', draft)
    first = json.loads((HERE / draft['cases'][0]['construction']).read_text())
    for item in first['files']:
        if item['path'] in ('runner.py', 'config.json'):
            (HERE / item['path']).write_text(item['content'])
    write(HERE / 'construction.json', first)
    print(json.dumps({entry['case_id']: entry['construction_sha256'] for entry in draft['cases']}))


if __name__ == '__main__':
    main()
