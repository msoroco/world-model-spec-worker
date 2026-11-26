"""Exercise four fixed-condition pair audits with synthetic source-shaped CPU packets."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from comparison_delivery_audit import audit_pair

spec = importlib.util.spec_from_file_location('c276263_prove_delivery', HERE / 'prove-delivery.py')
proof_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof_module)


def main():
    results = []
    for suffix in ('contrast', 'engine_on', 'brake_unset', 'wheel_straight'):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve(), prefix='c276263-pair-proof-') as temp:
            root = Path(temp)
            reference, contrast = root / 'reference', root / suffix
            proof_module.make_fixture('reference', reference)
            proof_module.make_fixture(suffix, contrast)
            audit = audit_pair(reference, contrast,
                              reference / 'physical-review.json',
                              contrast / 'physical-review.json', suffix)
            result = {'format': 'c276263-comparison-cpu-proof-v1',
                      'comparison_id': HERE.name + '__comparison_' + ('main' if suffix == 'contrast' else suffix),
                      'reference_case_id': HERE.name + '__reference',
                      'contrast_case_id': HERE.name + '__' + suffix,
                      'synthetic_cpu_fixture': True, 'original_native_executed': False,
                      'passed': audit['passed'],
                      'fixed_checks': audit['comparison']['fixed_checks'],
                      'difference_checks': audit['comparison'].get('difference_checks', {}),
                      'isolated_duty': audit['comparison'].get('duty'),
                      'physical_or_legal_acceptance': False}
            if not all(result['fixed_checks'].values()):
                raise ValueError('Fixed-condition CPU comparison absent')
            path = HERE / 'proofs' / ('comparison-' + suffix + '.json')
            path.write_text(json.dumps(result, indent=2) + '\n')
            results.append(result['comparison_id'])
    print(json.dumps({'passed': len(results), 'comparison_ids': results,
                      'synthetic_cpu_fixture': True}))


if __name__ == '__main__':
    main()
