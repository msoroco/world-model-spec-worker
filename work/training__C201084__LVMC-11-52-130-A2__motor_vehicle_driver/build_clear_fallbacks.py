"""Three source-triggered controller alternatives for the clear-lead probe."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT = {'same_path_half_width_m': 1.8, 'stop_gap_m': 6.0,
           'deceleration_mps2': 3.0, 'cruise_throttle': 0.28}
OPTIONS = (
    ('fallback1', {'stop_gap_m': 8.0},
     'Ego closes inside the six metre lead gap before settling',
     'lead longitudinal gap before near-zero ego speed',
     'gap drops below 6 m while ego speed exceeds 0.05 m/s'),
    ('fallback2', {'deceleration_mps2': 2.0},
     'Lead-relative closing speed exceeds the nominal braking envelope',
     'closing speed and lead gap over the approach',
     'predicted stop distance exceeds retained longitudinal gap'),
    ('fallback3', {'cruise_throttle': 0.18},
     'Ego approaches the lead too quickly before the braking request',
     'ego speed before first saved brake request',
     'ego speed exceeds 4 m/s before the first brake request'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    draft = json.loads((HERE/'draft-clear-manifest.json').read_text())
    entry = copy.deepcopy(draft['cases'][0])
    primary = json.loads((HERE/entry['construction']).read_text())
    if sha(HERE/entry['construction']) != entry['construction_sha256']:
        raise ValueError('Clear-lead primary changed before fallback construction')
    entry['candidate_risk'] = {
        'status': 'physical',
        'reason': 'Lead gap, closing speed and approach speed are separately observed Native motion risks; select alternatives only from source-measured failures.'}
    candidates = []
    for ident, changes, reason, metric, failure in OPTIONS:
        construction = copy.deepcopy(primary)
        config_file = next(item for item in construction['files']
                           if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = ident
        config['conflict_controller_tuning'] = {**DEFAULT, **changes}
        config_file['content'] = json.dumps(config, indent=2, sort_keys=True)+'\n'
        construction['status'] = 'draft_fallback_cpu_preparation_incomplete'
        construction['candidate_id'] = ident
        construction['mechanisms'] = primary['mechanisms'] + [
            ident+': '+reason+'; controller tuning '+json.dumps(changes, sort_keys=True)]
        name = 'draft-clear-'+ident+'-construction.json'
        write(HERE/name, construction)
        candidates.append({
            'id': ident, 'construction': name,
            'construction_sha256': sha(HERE/name),
            'trigger': {'source': 'native-actors.jsonl',
                        'metric': metric, 'failure_condition': failure},
            'changed_knobs': [f'{key}: {DEFAULT[key]} -> {value}'
                              for key, value in changes.items()]})
    entry['candidates'] = candidates
    draft['cases'] = [entry]
    draft['status'] = 'draft_clear_four_candidate_diagnostic'
    name = HERE/'draft-clear-fallback-manifest.json'
    write(name, draft)
    return {'manifest_sha256': sha(name),
            'candidates': {item['id']: item['construction_sha256']
                           for item in candidates}}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
