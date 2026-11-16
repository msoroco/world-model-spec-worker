"""Build three exact-case tour-bus alternatives from the proven primary package."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + '__tour_bus_below'
OPTIONS = (
    ('fallback1', 38, 'standard',
     'observed Native bus body overshoots the painted red curb target'),
    ('fallback2', 40, 'elevated_overview',
     'decoded overview hides the signed curb or complete bus body'),
    ('fallback3', 42, 'standard',
     'observed Native bus body stops short of the painted red curb target'),
)


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    original = json.loads((ROOT / 'selected-primary/tour_bus_below/construction.json').read_text())
    result = []
    for ident, target_x, camera_policy, trigger in OPTIONS:
        construction = json.loads(json.dumps(original))
        files = {item['path']: item['content'] for item in construction['files']}
        cfg = json.loads(files['config.json'])
        cfg['candidate_id'] = ident
        cfg['requested_target_x_m'] = target_x
        cfg['camera_policy'] = camera_policy
        cfg['risk_trigger'] = trigger
        rows = [json.loads(line) for line in files['requested-tracks.jsonl'].splitlines()]
        if len(rows) != cfg['requested_approach_frames'] or len(rows) != 120:
            raise ValueError('Tour-bus source approach changed')
        for i, row in enumerate(rows):
            row['requested_ego_x_m'] = round(5 + (target_x - 5) * (i + 1) / len(rows), 6)
        files['requested-tracks.jsonl'] = ''.join(
            json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)
        cfg['tracks_sha256'] = sha(files['requested-tracks.jsonl'])
        files['config.json'] = encoded(cfg)
        files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
            "self.assertEqual(cfg['requested_target_x_m'],40)",
            f"self.assertEqual(cfg['requested_target_x_m'],{target_x})")
        construction['files'] = [{'path': name, 'content': content}
                                 for name, content in files.items()]
        path = ROOT / 'selected-fallbacks/tour_bus_below' / ident / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded(construction))
        result.append({'id': ident, 'construction': str(path.relative_to(ROOT)),
                       'construction_sha256': sha(path.read_text()),
                       'requested_target_x_m': target_x,
                       'camera_policy': camera_policy})
    return result


if __name__ == '__main__':
    print(encoded(build()), end='')
