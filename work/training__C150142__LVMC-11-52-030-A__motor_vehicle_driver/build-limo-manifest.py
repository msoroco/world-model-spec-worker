"""Bind provisional limousine construction hashes for CPU offline checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = ('below', 'at', 'above', 'no_loading')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads((ROOT / 'execution-manifest-diagnostic-shuttle_bus_below-draft.json').read_text())
    entries = []
    for boundary in BOUNDARIES:
        prior = next(row for row in source['cases']
                     if row['case_id'].endswith('__shuttle_bus_' + boundary))
        row = json.loads(json.dumps(prior))
        case = 'limo_' + boundary
        row['case_id'] = ROOT.name + '__' + case
        row['construction'] = 'selected-primary/' + case + '/construction.json'
        row['construction_sha256'] = sha(ROOT / row['construction'])
        row.pop('offline', None)
        row['candidate_risk']['reason'] = (
            'Long provisional limo-service capture may miss passenger activity, '
            'sign visibility or stop timing. A sedan does not establish qualifying '
            'limousine service or a limousine body.')
        for candidate in row['candidates']:
            ident = candidate['id']
            candidate['construction'] = (
                f'selected-fallbacks/{case}/{ident}/construction.json')
            candidate['construction_sha256'] = sha(ROOT / candidate['construction'])
            candidate.pop('offline', None)
            candidate['trigger']['failure_condition'] = (
                candidate['trigger']['failure_condition']
                .replace('shuttle-service bus body', 'provisional limo-service sedan body'))
        entries.append(row)
    manifest = {'format': source['format'],
                'assignment_id': source['assignment_id'],
                'status': 'draft_selected_cpu', 'cases': entries,
                'runtime_manifest_sha256': source['runtime_manifest_sha256']}
    output = ROOT / 'execution-manifest-diagnostic-limo_below-draft.json'
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'manifest': str(output.relative_to(ROOT)), 'sha256': sha(output),
            'cases': [row['case_id'] for row in entries],
            'candidates_per_case': 4}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
