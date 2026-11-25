"""Verify retained current-runtime positive and negative fallback receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'selected_measurements',
          'negative_case_source', 'four_camera_sources'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for response in ('avoid', 'no_conflict'):
        here = ROOT / ('selected-exception-c-' + response)
        case = ROOT.name + '__exception_c_' + response
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        recipe = ROOT.parents[1] / entry['fixture_recipe']
        primary = json.loads((here / 'compatibility.json').read_text())
        receipts = []
        for candidate in entry['candidates']:
            ident = candidate['id']
            folder = here / (ident + '-proof')
            receipt_path = folder / 'receipt.json'
            receipt = json.loads(receipt_path.read_text())
            construction = ROOT / candidate['construction']
            if sha(construction) != candidate['construction_sha256']:
                raise ValueError('Selected exception C construction changed: ' + ident)
            for key, expected in (('case_id', case), ('candidate_id', ident),
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
            receipts.append({'candidate_id': ident, 'receipt_sha256': sha(receipt_path),
                             'construction_sha256': candidate['construction_sha256'],
                             'positive_negative_passed': True})
        proof = {'format': 'c10052-selected-exception-c-fallback-cpu-audit-v1',
                 'case_id': case, 'candidate_receipts': receipts,
                 'diagnostic_only': True, 'original_native_observed': False}
        (here / 'fallback-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
        print(case, len(receipts), 'passed')


if __name__ == '__main__':
    main()
