"""Bind exact shuttle-bus construction hashes for offline diagnostic proofs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = ('below', 'at', 'above', 'no_loading')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    prior = json.loads((ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json').read_text())
    entries = []
    for boundary in BOUNDARIES:
        source = next(c for c in prior['cases'] if c['case_id'].endswith('__tour_bus_' + boundary))
        entry = json.loads(json.dumps(source))
        case = 'shuttle_bus_' + boundary
        entry['case_id'] = ROOT.name + '__' + case
        entry['construction'] = 'selected-primary/' + case + '/construction.json'
        entry['construction_sha256'] = digest(ROOT / entry['construction'])
        entry['candidate_risk']['reason'] = (
            'Long shuttle-service capture may miss passenger proximity, signed curb '
            'visibility or stop timing in Native; service identity remains unverified')
        entry.pop('offline', None)
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate['construction'] = (
                'selected-fallbacks/' + case + '/' + ident + '/construction.json')
            candidate['construction_sha256'] = digest(ROOT / candidate['construction'])
            candidate.pop('offline', None)
            candidate['trigger']['failure_condition'] = candidate['trigger'][
                'failure_condition'].replace('bus body', 'shuttle-service bus body')
        entries.append(entry)
    manifest = {'format': prior['format'], 'assignment_id': prior['assignment_id'],
                'status': 'draft_selected_cpu', 'cases': entries,
                'runtime_manifest_sha256': prior['runtime_manifest_sha256']}
    output = ROOT / 'execution-manifest-diagnostic-shuttle_bus_below-draft.json'
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'manifest': str(output.relative_to(ROOT)), 'sha256': digest(output),
            'cases': [entry['case_id'] for entry in entries], 'candidates_per_case': 4}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
