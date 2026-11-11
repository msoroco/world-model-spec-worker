"""Bind three distinct first-case physical-risk fallback constructions."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def change_file(construction, name, old, new):
    files = [item for item in construction['files'] if item['path'] == name]
    if len(files) != 1 or files[0]['content'].count(old) != 1:
        raise ValueError('Fallback source anchor changed: ' + name)
    files[0]['content'] = files[0]['content'].replace(old, new)


def build():
    source = json.loads((HERE / 'night-probes/night_299_upper-construction.json').read_text())
    base = json.loads((HERE / 'night-299-execution-manifest.json').read_text())
    entry = base['cases'][0]
    variants = [
        ('fallback1', 'native_headlamp_probe.py',
         "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])",
         "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], step_m=1.25)",
         'Original Native waypoint route selector reports no connected 2.5 m sample route',
         'connected eligible route count',
         'Primary route selector finds zero connected 299 ft same-lane routes',
         'waypoint sampling 2.5 m to 1.25 m'),
        ('fallback2', 'native_headlamp_probe.py',
         'def _command(actor, target, speed=6):',
         'def _command(actor, target, speed=5):',
         'retained original subject and lead velocity plus body-gap rows',
         'measured 20 Hz gap oscillation and tracking error',
         'Primary 6 m/s command fails the predeclared ±2 ft engineering attainment screen',
         'target cruise speed 6 m/s to 5 m/s'),
        ('fallback3', 'headlamp_camera.py',
         '"overview": ((-32, 0, 10), (-4, 0, 0), (1920, 1080), 95)',
         '"overview": ((-36, 0, 12), (-4, 0, 0), (1920, 1080), 95)',
         'original overview source-pixel review',
         'complete subject and lead body visibility across all frames',
         'Primary overview camera omits either required full body in any reviewed frame',
         'overview mount from (-32,0,10) m to (-36,0,12) m'),
    ]
    candidates = []
    for ident, filename, old, new, trigger_source, metric, failure, knob in variants:
        construction = json.loads(json.dumps(source))
        change_file(construction, filename, old, new)
        relative = f'night-probes/night_299_upper-{ident}-construction.json'
        path = HERE / relative
        path.write_text(json.dumps(construction, indent=2) + '\n')
        candidates.append({'id': ident, 'construction': relative,
                           'construction_sha256': sha(path),
                           'trigger': {'source': trigger_source, 'metric': metric,
                                       'failure_condition': failure},
                           'changed_knobs': [knob]})
    entry['candidates'] = candidates
    (HERE / 'night-fallback-manifest.json').write_text(json.dumps(base, indent=2) + '\n')


if __name__ == '__main__':
    build()
