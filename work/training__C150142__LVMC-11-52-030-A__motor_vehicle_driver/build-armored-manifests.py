"""Bind all armored visual-proxy draft candidates to diagnostic manifests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    result = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            old = 'emergency_vehicle_' + sign + '_' + activity
            new = 'armored_car_' + sign + '_' + activity
            source_slug = 'emergency-' + ('signed-' if sign == 'signed' else '') + (
                'business' if activity == 'business' else 'no-business')
            source = json.loads((ROOT / ('execution-manifest-diagnostic-' +
                                          source_slug + '-draft.json')).read_text())
            if len(source['cases']) != 1 or not source['cases'][0]['case_id'].endswith('__' + old):
                raise ValueError('Emergency manifest source differs')
            entry = source['cases'][0]
            entry['case_id'] = ROOT.name + '__' + new
            entry['construction'] = entry['construction'].replace(old, new)
            entry['construction_sha256'] = sha(ROOT / entry['construction'])
            entry['candidate_risk']['reason'] += (
                '; attached-panel proxy appearance and actual armored identity unverified')
            for candidate in entry['candidates']:
                candidate['construction'] = candidate['construction'].replace(old, new)
                candidate['construction_sha256'] = sha(ROOT / candidate['construction'])
            target = ROOT / ('execution-manifest-diagnostic-' + new + '-draft.json')
            target.write_text(json.dumps(source, indent=2, allow_nan=False) + '\n')
            result.append({'case_id': entry['case_id'],
                           'manifest': str(target.relative_to(ROOT)),
                           'sha256': sha(target), 'candidates': 4})
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
