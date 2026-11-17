"""Bind exact emergency-business draft candidates for pinned CPU checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = 'emergency_vehicle_unsigned_business'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads((ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json').read_text())
    entry = next(row for row in source['cases']
                 if row['case_id'].endswith('__tour_bus_below'))
    entry = json.loads(json.dumps(entry))
    entry['case_id'] = ROOT.name + '__' + CASE
    entry['construction'] = 'selected-primary/' + CASE + '/construction.json'
    entry['construction_sha256'] = digest(ROOT / entry['construction'])
    entry['candidate_risk']['reason'] = (
        'Native firetruck stop may overshoot red paint; overview may hide body '
        'or service-worker approach, and the worker may fail to dwell or depart')
    entry.pop('offline', None)
    for candidate in entry['candidates']:
        ident = candidate['id']
        candidate['construction'] = (
            'selected-fallbacks/' + CASE + '/' + ident + '/construction.json')
        candidate['construction_sha256'] = digest(ROOT / candidate['construction'])
        candidate.pop('offline', None)
        trigger = candidate['trigger']
        for field in ('source', 'metric', 'failure_condition'):
            trigger[field] = trigger[field].replace('bus body', 'firetruck body').replace(
                'signed curb', 'red curb').replace('sign, ', '')
    manifest = {'format': source['format'], 'assignment_id': source['assignment_id'],
                'status': 'draft_selected_cpu', 'cases': [entry],
                'runtime_manifest_sha256': source['runtime_manifest_sha256']}
    output = ROOT / 'execution-manifest-diagnostic-emergency-business-draft.json'
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'manifest': str(output.relative_to(ROOT)), 'sha256': digest(output),
            'case_id': entry['case_id'], 'candidates': 4}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
