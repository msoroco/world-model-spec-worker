"""Replay all six exact recorded-pair comparison paths on saved CPU attempts.

The fixtures are synthetic. A positive replay proves source-bound software
behavior only; the per-pair mutation tests the fixed-condition rejection path.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import stop_reference_comparison as comparison

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(attempt_root):
    attempt_root = Path(attempt_root).resolve()
    if not attempt_root.is_dir():
        raise ValueError('Saved six-case attempt root missing')
    results = []
    original_audit = comparison.audit_delivery
    for name, (left, right, _) in comparison.RECORDED_PAIRS.items():
        left_path, right_path = attempt_root / left, attempt_root / right
        positive = comparison.compare_recorded(name, left_path, right_path,
                                               diagnostic=True)
        if (positive.get('comparison_id') != name
                or positive.get('software_checks_passed') is not True
                or positive.get('diagnostic_only') is not True
                or positive.get('physical_acceptance_claimed') is not False
                or positive.get('legal_acceptance_claimed') is not False):
            raise ValueError('Recorded diagnostic comparison receipt invalid: ' + name)
        # The source delivery audits above have already checked both real
        # fixture directories. Isolate the comparison rejection branch using
        # a temporary mutated context without changing either saved attempt.
        with tempfile.TemporaryDirectory(prefix='c331230-pair-negative-') as tmp:
            changed = Path(tmp)
            context = json.loads((right_path / 'approach_context.json').read_text())
            context['native_stop_sign_id'] = int(context['native_stop_sign_id']) + 1000
            (changed / 'approach_context.json').write_text(json.dumps(context) + '\n')
            comparison.audit_delivery = lambda case_id, root, **kwargs: {'case_id': case_id}
            try:
                try:
                    comparison.compare_recorded(name, left_path, changed,
                                                diagnostic=True)
                except ValueError as error:
                    if 'Fixed source condition differs: native_stop_sign_id' not in str(error):
                        raise ValueError('Unexpected pair rejection: ' + str(error)) from error
                    negative = str(error)
                else:
                    raise ValueError('Changed fixed stop-sign identity escaped: ' + name)
            finally:
                comparison.audit_delivery = original_audit
        results.append({'comparison_id': name, 'case_ids': positive['case_ids'],
                        'left_context_sha256': sha(left_path / 'approach_context.json'),
                        'right_context_sha256': sha(right_path / 'approach_context.json'),
                        'positive': positive, 'negative_error': negative})
    return {'format': 'worker-c331230-six-pair-cpu-proof',
            'comparison_auditor_sha256': sha(ROOT / 'stop_reference_comparison.py'),
            'delivery_auditor_sha256': sha(ROOT / 'delivery_audit.py'),
            'attempt_root': str(attempt_root), 'pairs': results,
            'all_six_software_paths_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    receipt = prove(args.attempt_root)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'pairs': len(receipt['pairs']), 'passed': True,
                      'output': args.output}))
