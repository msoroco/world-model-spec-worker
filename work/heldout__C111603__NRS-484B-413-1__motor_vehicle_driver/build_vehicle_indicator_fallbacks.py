"""Three source-triggered alternate constructions for the exact indicator case."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
primary = json.loads((ROOT / 'vehicle-indicator-construction.json').read_text())
manifest_path = ROOT / 'vehicle-indicator-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = manifest['cases'][0]


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


definitions = (
    ('fallback1', 'Native connected left-turn route inventory',
     'eligible left-turn routes at 2 m sampling',
     'Primary route sampling finds no connected left turn',
     ['route sampling 2 m/6 steps to 1.5 m/8 steps']),
    ('fallback2', 'Original ego speed, yaw and indicator readback',
     'approach speed settling and turn onset frames',
     'Primary 5 m/s approach destabilizes the signal-before-turn timing',
     ['target speed 5 to 4 m/s and gain .25 to .2']),
    ('fallback3', 'Original overview RGB decode',
     'ego, affected vehicle and lamp visible pixel count',
     'Primary overview mount crops participant or indicator visibility',
     ['overview camera mount x -8 to -9 m']),
)
fallbacks = []
for name, source, metric, condition, knobs in definitions:
    construction = deepcopy(primary)
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    if name == 'fallback1':
        config['engineering']['route_spacing_m'] = 1.5
        config['engineering']['approach_steps'] = 8
    elif name == 'fallback2':
        config['engineering']['target_speed_mps'] = 4.
        config['engineering']['speed_gain'] = .2
    else:
        camera = next(item for item in construction['files'] if item['path'] == 'turn_camera_capture.py')
        original = '"overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
        revised = '"overview": ((-9, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
        if camera['content'].count(original) != 1:
            raise ValueError('Overview fallback camera mount source changed')
        camera['content'] = camera['content'].replace(original, revised)
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    path = ROOT / ('vehicle-indicator-' + name + '-construction.json')
    save(path, construction)
    fallbacks.append({'id': name, 'construction': path.name,
                      'construction_sha256': sha256(path.read_bytes()).hexdigest(),
                      'trigger': {'source': source, 'metric': metric,
                                  'failure_condition': condition},
                      'changed_knobs': knobs})
entry['candidates'] = fallbacks
save(manifest_path, manifest)
print('Three exact indicator fallback constructions authored')
