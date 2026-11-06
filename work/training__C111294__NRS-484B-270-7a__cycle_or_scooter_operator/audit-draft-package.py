"""Independent exact-bundle portable receipt and negative audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    summary = json.loads((HERE / 'draft-package-summary.json').read_text())
    records = {(r['case_id'], r['candidate_id']): r for r in summary['results']}
    if len(records) != 8:
        raise ValueError('Eight exact portable receipts required')
    checked = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                r for r in entry['candidates'] if r['id'] == candidate)
            folder = HERE / 'draft-candidates' / suffix / candidate
            construction = folder / 'construction.json'
            if sha(construction) != selected['construction_sha256']:
                raise ValueError('Exact construction changed')
            package = json.loads((folder / 'package-receipt.json').read_text())
            if package != records[(entry['case_id'], candidate)]:
                raise ValueError('Portable summary differs from receipt')
            receipt = package['receipt']
            if receipt['format'] != 'worker-package-compatibility-v1' or receipt['passed'] is not True or \
                    receipt['candidate_id'] != candidate or receipt['case_id'] != entry['case_id'] or \
                    receipt['construction_sha256'] != selected['construction_sha256'] or \
                    receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']:
                raise ValueError('Exact portable identity or pass differs')
            expected = {'actual_analysis', 'native_validation', 'mandatory_observations',
                        'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged'}
            if not expected.issubset(receipt['checks']):
                raise ValueError('Portable check set incomplete')
            if sha(folder / 'package-analysis.log') != receipt['log_sha256']:
                raise ValueError('Saved analysis log changed')
            if package['negative']['removed'] != 'interaction.json' or \
                    package['negative']['exit_code'] == 0 or \
                    package['negative']['error_contains'] not in (folder / 'package-negative.log').read_text():
                raise ValueError('Missing source negative absent')
            checked.append({'case': suffix, 'candidate': candidate,
                            'construction_sha256': selected['construction_sha256']})
    return {'passed': True, 'exact_unselected_portable_candidates': checked,
            'physical_or_selected_claim': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
