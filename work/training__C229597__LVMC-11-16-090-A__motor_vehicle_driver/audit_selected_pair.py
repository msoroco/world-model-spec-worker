"""Check all eight returned selected CPU compatibility receipts."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((P / 'selected-pair-manifest.json').read_text())
    records = []
    for entry in manifest['cases']:
        for candidate in [dict(entry, id='primary'), *entry['candidates']]:
            proof_spec = candidate['compatibility']
            path = P / proof_spec['receipt']
            proof = json.loads(path.read_text())
            if (sha(path) != proof_spec['sha256'] or proof['passed'] is not True
                    or proof['case_id'] != entry['case_id']
                    or proof['candidate_id'] != candidate['id']
                    or proof['construction_sha256'] != candidate['construction_sha256']
                    or proof['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']
                    or not CHECKS <= set(proof['checks'])
                    or sha(P / candidate['construction']) != candidate['construction_sha256']
                    or sha(P / proof_spec['log']) != proof['log_sha256']
                    or sha(P / proof_spec['negative_log']) != proof['negative_log_sha256']
                    or proof['negative_removed'] != 'acquisition-provenance.json'
                    or proof['negative_error_contains'] not in (P / proof_spec['negative_log']).read_text()):
                raise ValueError('Selected receipt differs: ' + entry['case_id'] + '/' + candidate['id'])
            records.append({'case_id': entry['case_id'], 'candidate_id': candidate['id'],
                            'receipt_sha256': sha(path),
                            'speed_increase_mps': proof['measurement_examples']['text_0_motion']['value']['speed_increase_mps']})
    if len(records) != 8:
        raise ValueError('Incomplete selected pair')
    output = {'format': 'c229597-selected-pair-cpu-audit-v1',
              'manifest_sha256': sha(P / 'selected-pair-manifest.json'),
              'receipts_checked': len(records), 'records': records,
              'synthetic_only': True, 'native_executed': False,
              'delivery_ready': False}
    (P / 'selected-pair-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'receipts_checked': len(records), 'passed': True}))


if __name__ == '__main__':
    main()
