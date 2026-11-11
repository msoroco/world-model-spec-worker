"""Freeze three physically triggered variants of the stopped drive-to case."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = HERE / 'cases/stopped_drive_to_500ft'
MANIFEST = HERE / 'execution-manifest.json'
CASE = HERE.name + '__stopped_drive_to_500ft'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def one(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one variant knob: ' + old)
    return text.replace(old, new)


base = json.loads((DEST / 'construction.json').read_text())
manifest = json.loads(MANIFEST.read_text())
entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
variants = [
    ('fallback1', 'runner.py',
     'target_gap_ft=520)', 'target_gap_ft=520, step_m=2.5)',
     'Native waypoint route-selection diagnostic',
     'unique connected through-intersection approach route',
     'Primary 5 m sampling finds no unique connected route; resolve available geometry at 2.5 m sampling.',
     'route waypoint sampling step: 5 m to 2.5 m'),
    ('fallback2', 'runner.py',
     'target_distance_ft=500,\n                          steer=',
     'target_distance_ft=500, gain=0.22,\n                          steer=',
     'retained original participant_footprints.jsonl and participant_state.jsonl',
     'active-frame centre-distance approach overshoot',
     'Primary approach overshoots the 500 ft engineering target by more than 2 ft in consecutive active frames.',
     'approach controller gain: 0.35 to 0.22'),
    ('fallback3', 'fire_camera_capture.py',
     '"approach": ((1.2, 0.0, 2.0)',
     '"approach": ((1.8, 0.0, 2.3)',
     'complete decoded approach and overview original RGB streams',
     'participant body visibility throughout the approach',
     'Primary approach view omits a required body in an original frame, confirmed by original-pixel review.',
     'approach camera mount: 1.2 m forward/2.0 m high to 1.8 m forward/2.3 m high'),
]
entry['candidates'] = []
for ident, path, old, new, source, metric, condition, knob in variants:
    construction = deepcopy(base)
    files = {item['path']: item for item in construction['files']}
    files[path]['content'] = one(files[path]['content'], old, new)
    construction['files'] = list(files.values())
    destination = DEST / (ident + '-construction.json')
    save(destination, construction)
    entry['candidates'].append({
        'id': ident, 'construction': destination.relative_to(HERE).as_posix(),
        'construction_sha256': sha(destination),
        'trigger': {'source': source, 'metric': metric, 'failure_condition': condition},
        'changed_knobs': [knob]})
save(MANIFEST, manifest)
