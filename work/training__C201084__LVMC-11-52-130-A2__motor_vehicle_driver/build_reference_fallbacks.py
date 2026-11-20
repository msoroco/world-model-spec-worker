"""Build three risk-specific Native controller alternatives for the reference case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


DEFAULT = {'stop_radius_m': 0.8, 'cruise_mps': 4.0,
           'deceleration_mps2': 2.0, 'following_brake_gap_m': 7.0,
           'following_cruise_throttle': 0.32}
OPTIONS = (
    ('fallback1', {'deceleration_mps2': 3.0},
     'Ego passes the authored stop centre before sustained near-zero motion',
     'native-actors.jsonl', 'ego body-centre overshoot after target braking',
     'ego body centre exceeds stop centre by 0.8 m before near-zero speed'),
    ('fallback2', {'stop_radius_m': 1.2, 'cruise_mps': 3.0},
     'Ego remains moving through the target zone after the nominal approach',
     'native-actors.jsonl', 'near-zero samples inside authored target zone',
     'no near-zero sample with body overlap in the 600-frame capture'),
    ('fallback3', {'following_brake_gap_m': 10.0,
                   'following_cruise_throttle': 0.24},
     'Following vehicle closes too near the ego during the destination stop',
     'native-actors.jsonl', 'minimum retained following gap in metres',
     'following_gap_m drops below 7.0 m before the ego stop'),
)


def build():
    draft = json.loads((HERE/'draft-reference-manifest.json').read_text())
    entry = copy.deepcopy(draft['cases'][0])
    primary = json.loads((HERE/entry['construction']).read_text())
    if sha(HERE/entry['construction']) != entry['construction_sha256']:
        raise ValueError('Primary changed before fallback construction')
    entry['candidate_risk'] = {
        'status': 'physical',
        'reason': 'Stop-point overshoot, insufficient settled samples and follower closing are distinct Native motion risks; select alternatives from source-measured failures only.'}
    candidates = []
    for ident, changes, reason, source, metric, failure in OPTIONS:
        construction = copy.deepcopy(primary)
        config_file = next(item for item in construction['files']
                           if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = ident
        config['controller_tuning'] = {**DEFAULT, **changes}
        config_file['content'] = json.dumps(config, indent=2, sort_keys=True)+'\n'
        construction['status'] = 'draft_fallback_cpu_preparation_incomplete'
        construction['candidate_id'] = ident
        construction['mechanisms'] = primary['mechanisms'] + [
            ident+': '+reason+'; controller tuning '+json.dumps(changes, sort_keys=True)]
        name = f'draft-reference-{ident}-construction.json'
        write(HERE/name, construction)
        candidates.append({'id': ident, 'construction': name,
                           'construction_sha256': sha(HERE/name),
                           'trigger': {'source': source, 'metric': metric,
                                       'failure_condition': failure},
                           'changed_knobs': [f'{key}: {DEFAULT[key]} -> {value}'
                                             for key, value in changes.items()]})
    entry['candidates'] = candidates
    draft['cases'] = [entry]
    draft['status'] = 'draft_reference_four_candidate_diagnostic'
    name = HERE/'draft-reference-fallback-manifest.json'
    write(name, draft)
    return {'manifest_sha256': sha(name),
            'candidates': {item['id']: item['construction_sha256']
                           for item in candidates}}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
