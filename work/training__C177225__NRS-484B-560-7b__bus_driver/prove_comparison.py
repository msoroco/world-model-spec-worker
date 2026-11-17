"""Source-bound CPU proof of the declared saved reference/contrast difference."""
import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from finalize_direction import process_saved, signal_case_id


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(reference, contrast, output, *, source_kind):
    roots = {'reference': Path(reference), 'contrast': Path(contrast)}
    observations = {name: process_saved(root, source_kind=source_kind)
                    for name, root in roots.items()}
    configs = {name: json.loads((root / 'config.json').read_text())
               for name, root in roots.items()}
    signals = {name: json.loads((root / 'officer_signal_definition.json').read_text())
               for name, root in roots.items()}
    audit = audit_pair(observations['reference'], observations['contrast'],
                      configs['reference'], configs['contrast'],
                      signals['reference'], signals['contrast'])
    if audit['status'] != 'software_measurement_pair_observed':
        raise ValueError('Saved comparison response difference not established')
    receipts = {}
    for name, root in roots.items():
        expected = name == 'reference'
        result = json.loads((root / 'result.json').read_text())
        compatibility = json.loads((root / 'compatibility.json').read_text())
        checks = [item for item in result['target_checks']
                  if item['target'] == 'bus_obeys_officer_direction']
        if (len(checks) != 1 or checks[0]['requested'] is not expected or
                checks[0]['measured'] is not expected or
                checks[0]['matched'] is not True or
                checks[0]['physical_cause_confirmed'] is not False or
                result['case_id'] != signal_case_id(name) or
                result['provenance_kind'] != 'synthetic_fixture' or
                compatibility['case_id'] != result['case_id'] or
                compatibility['passed'] is not True):
            raise ValueError('Comparison result or compatibility proof differs: ' + name)
        receipts[name] = {
            'case_id': result['case_id'],
            'construction_sha256': compatibility['construction_sha256'],
            'compatibility_sha256': sha(root / 'compatibility.json'),
            'result_sha256': sha(root / 'result.json'),
            'raw_source_sha256': observations[name]['saved_source_sha256'],
            'camera_source_sha256': {view: source['sha256'] for view, source in
                                     observations[name]['saved_camera_sources'].items()},
            'observed_complete_stop_before_line':
                observations[name]['observed_complete_stop_before_line'],
            'observed_crossing_entry': observations[name]['observed_crossing_entry'],
        }
    proof = {'format': 'c177225-source-bound-comparison-diagnostic-v1',
             'audit': audit, 'cases': receipts, 'passed': True,
             'scope': '600-frame synthetic_native_sample CPU diagnostic only',
             'physical_acceptance_claimed': False,
             'legal_acceptance_claimed': False}
    target = Path(output)
    if target.exists():
        raise ValueError('Retain prior comparison proof')
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-kind', default='synthetic_native_sample',
                        choices=('synthetic_native_sample', 'original_native'))
    args = parser.parse_args()
    print(json.dumps(prove(args.reference, args.contrast, args.output,
                           source_kind=args.source_kind)))
