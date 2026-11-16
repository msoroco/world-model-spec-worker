"""Three same-case signed red-curb alternatives with distinct physical triggers."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + '__ordinary_red_signed'
RISKS = {
    'fallback1': {
        'source': 'Native body centers and signed red-curb extent',
        'metric': 'longitudinal parking overshoot in m',
        'failure_condition': 'Observed ego passes the signed curb target before stopping',
        'changed_knobs': ['requested_approach_frames', 'controller approach speed']},
    'fallback2': {
        'source': 'decoded overview pixels and Native signal readback',
        'metric': 'visible sign, red paint and complete ego body',
        'failure_condition': 'Sign or body is obscured in the source overview',
        'changed_knobs': ['overview camera elevation']},
    'fallback3': {
        'source': 'Native stationary body interval and four-view frame join',
        'metric': 'signed red-curb stationary interval in frames',
        'failure_condition': 'Stopped interval is too short for manual signed-curb review',
        'changed_knobs': ['requested_approach_frames', 'controller approach speed']}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def build():
    source = ROOT / 'selected-primary/ordinary_red_signed/construction.json'
    primary = json.loads(source.read_text())
    if primary['case_id'] != CASE:
        raise ValueError('Signed primary changed')
    source_config = json.loads(next(f['content'] for f in primary['files']
                                    if f['path'] == 'config.json'))
    entries = []
    for candidate, risk in RISKS.items():
        ordinary = json.loads((ROOT / 'selected-fallbacks/reference' /
                               candidate / 'construction.json').read_text())
        ordinary_files = {f['path']: f['content'] for f in ordinary['files']}
        ordinary_config = json.loads(ordinary_files['config.json'])
        alt = copy.deepcopy(primary)
        files = {f['path']: f for f in alt['files']}
        cfg = copy.deepcopy(source_config)
        for key in ('candidate_id', 'tracks_sha256', 'requested_approach_frames',
                    'camera_policy', 'risk_trigger'):
            cfg[key] = ordinary_config[key]
        files['config.json']['content'] = encode(cfg)
        files['requested-tracks.jsonl']['content'] = ordinary_files['requested-tracks.jsonl']
        path = ROOT / 'selected-fallbacks/ordinary_red_signed' / candidate / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encode(alt))
        entries.append({'id': candidate,
                        'construction': path.relative_to(ROOT).as_posix(),
                        'construction_sha256': sha(path),
                        'trigger': {key: risk[key] for key in
                                    ('source', 'metric', 'failure_condition')},
                        'changed_knobs': risk['changed_knobs']})
    manifest_path = ROOT / 'execution-manifest-diagnostic-ordinary_red_signed.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'][0]['candidates'] = entries
    manifest_path.write_text(encode(manifest))
    return {'case_id': CASE, 'fallbacks': [row['id'] for row in entries]}


if __name__ == '__main__':
    print(encode(build()), end='')
