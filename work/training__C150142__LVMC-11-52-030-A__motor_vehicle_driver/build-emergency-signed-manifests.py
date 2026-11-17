"""Bind both signed emergency draft pairs to the pinned CPU pipeline."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    result = []
    for suffix, old_slug, new_slug in (
            ('business', 'emergency-business', 'emergency-signed-business'),
            ('no_business', 'emergency-no-business', 'emergency-signed-no-business')):
        old = 'emergency_vehicle_unsigned_' + suffix
        new = 'emergency_vehicle_signed_' + suffix
        source = json.loads((ROOT / ('execution-manifest-diagnostic-' + old_slug + '-draft.json')).read_text())
        if len(source['cases']) != 1 or not source['cases'][0]['case_id'].endswith('__' + old):
            raise ValueError('Unsigned manifest source differs')
        entry = source['cases'][0]
        entry['case_id'] = ROOT.name + '__' + new
        entry['construction'] = entry['construction'].replace(old, new)
        entry['construction_sha256'] = digest(ROOT / entry['construction'])
        entry['candidate_risk']['reason'] += '; authored sign text and physical visibility are unreviewed'
        for candidate in entry['candidates']:
            candidate['construction'] = candidate['construction'].replace(old, new)
            candidate['construction_sha256'] = digest(ROOT / candidate['construction'])
        target = ROOT / ('execution-manifest-diagnostic-' + new_slug + '-draft.json')
        target.write_text(json.dumps(source, indent=2, allow_nan=False) + '\n')
        result.append({'case_id': entry['case_id'], 'manifest': str(target.relative_to(ROOT)),
                       'sha256': digest(target), 'candidates': 4})
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
