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
    primary_configs = []
    for entry in manifest['cases']:
        construction = json.loads((P / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        primary_configs.append(config)
        physical = json.loads((P / 'physical-preparation' /
                               entry['case_id'].rsplit('__', 1)[-1] / 'proof.json').read_text())
        saved = json.loads((P / 'selected-saved-proofs' /
                            entry['case_id'].rsplit('__', 1)[-1] / 'processing.json').read_text())
        if (physical['construction_sha256'] != entry['construction_sha256']
                or not physical['synthetic_fixture_only']
                or saved['analysis_revision']['construction_sha256'] != entry['construction_sha256']
                or not saved['passed'] or not saved['recorded_only']
                or saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
            raise ValueError('Selected physical/saved CPU proof differs: ' + entry['case_id'])
    reference, contrast = primary_configs
    for key in reference:
        if key not in ('case_id', 'selected_case_id', 'case', 'control_phases'):
            if reference[key] != contrast.get(key):
                raise ValueError('Unplanned comparison difference: ' + key)
    ref_phases, other_phases = reference['control_phases'], contrast['control_phases']
    if (len(ref_phases) != len(other_phases) or
            any({k: v for k, v in phase.items() if k != 'throttle'} !=
                {k: v for k, v in other.items() if k != 'throttle'}
                for phase, other in zip(ref_phases, other_phases)) or
            [i for i, (phase, other) in enumerate(zip(ref_phases, other_phases))
             if phase['throttle'] != other['throttle']] != [1, 2]):
        raise ValueError('Physical comparison changes more than selected throttle phases')
    case_stage = json.loads((P / 'proposals/cases.json').read_text())
    selected = [case for case in case_stage['cases'] if case['target_type'] != 'baseline']
    if (len(selected) != 2 or len({case['paired_probe_id'] for case in selected}) != 1
            or any(case['deliberate_differences'] != ['requested_throttle_profile']
                   for case in selected)):
        raise ValueError('Canonical comparison metadata differs')
    output = {'format': 'c229597-selected-pair-cpu-audit-v1',
              'manifest_sha256': sha(P / 'selected-pair-manifest.json'),
              'receipts_checked': len(records), 'records': records,
              'comparison_isolation_checked': True,
              'selected_saved_primaries_checked': 2,
              'physical_fixture_proofs_checked': 2,
              'synthetic_only': True, 'native_executed': False,
              'delivery_ready': False}
    (P / 'selected-pair-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'receipts_checked': len(records), 'passed': True}))


if __name__ == '__main__':
    main()
