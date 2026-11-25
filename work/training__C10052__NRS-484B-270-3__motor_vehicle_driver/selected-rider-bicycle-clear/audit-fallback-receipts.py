"""Independently bind both selected rider fallback CPU compatibility receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'selected_measurements',
          'negative_case_source', 'four_camera_sources'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = manifest['cases'][0]
    recipe = ROOT.parents[1] / entry['fixture_recipe']
    primary = json.loads((HERE / 'compatibility.json').read_text())
    rows = []
    for candidate in entry['candidates']:
        ident = candidate['id']
        folder = HERE / (ident + '-proof')
        receipt = json.loads((folder / 'receipt.json').read_text())
        construction = ROOT / candidate['construction']
        if sha(construction) != candidate['construction_sha256']:
            raise ValueError('Selected fallback construction changed: ' + ident)
        for key, expected in (
                ('case_id', entry['case_id']), ('candidate_id', ident),
                ('construction_sha256', candidate['construction_sha256']),
                ('runtime_manifest_sha256', manifest['runtime_manifest_sha256']),
                ('fixture_recipe_sha256', sha(recipe)),
                ('fixture_sha256', primary['fixture_sha256'])):
            if receipt.get(key) != expected:
                raise ValueError('Selected fallback proof changed: ' + ident + '/' + key)
        if (receipt.get('passed') is not True
                or not CHECKS <= set(receipt.get('checks', []))
                or sha(folder / 'analysis.log') != receipt['log_sha256']
                or sha(folder / 'negative.log') != receipt['negative_log_sha256']
                or receipt['negative_error_contains']
                not in (folder / 'negative.log').read_text()):
            raise ValueError('Selected fallback proof incomplete: ' + ident)
        rows.append({'candidate_id': ident, 'receipt_sha256': sha(folder / 'receipt.json'),
                     'construction_sha256': candidate['construction_sha256'],
                     'positive_negative_passed': True})
    proof = {'format': 'c10052-selected-rider-fallback-cpu-audit-v1',
             'case_id': entry['case_id'], 'candidate_receipts': rows,
             'diagnostic_only': True, 'original_native_observed': False}
    (HERE / 'fallback-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
