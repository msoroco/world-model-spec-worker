"""Run nine exact independent alley audits on marked saved CPU fixtures."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SUFFIXES = [f'{interest}_{speed}mps' for interest in ('person', 'property')
            for speed in (3, 5, 7)] + [f'alley_gap_judgment_sweep-{index:04d}'
                                      for index in range(3)]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(argv, path):
    result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    path.write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    entries = []
    script = ROOT / 'delivery_audit.py'
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        attempt = REPO / '.runtime-work' / f'c10364-{suffix}-saved-sourcepoint/v0001/analysis'
        positive = ROOT / f'delivery-audit-{suffix}-positive.log'
        negative = ROOT / f'delivery-audit-{suffix}-negative.log'
        base = [sys.executable, str(script), '--case', case_id, '--attempt', str(attempt),
                '--diagnostic-fixture']
        if run(base, positive):
            raise ValueError('Positive diagnostic delivery audit failed: ' + suffix)
        passed = json.loads(positive.read_text())
        if (passed.get('case_id') != case_id or passed.get('physical_acceptance_claimed')
                or passed.get('legal_acceptance_claimed')):
            raise ValueError('Diagnostic audit claimed acceptance: ' + suffix)
        tamper_path = REPO / '.runtime-work' / f'c10364-{suffix}-audit-tampered-report.json'
        tampered = json.loads((attempt / 'analysis-report.json').read_text())
        tampered['measurements']['alley_original_exposure']['value']['source_sha256'][
            'participant_footprints.jsonl'] = '0' * 64
        tamper_path.write_text(json.dumps(tampered, indent=2) + '\n')
        negative_argv = base + ['--report', str(tamper_path)]
        negative_exit = run(negative_argv, negative)
        if negative_exit == 0 or 'Saved result and analysis measurement differ' not in negative.read_text():
            raise ValueError('Tampered original hash was not rejected: ' + suffix)
        entries.append({'case_id': case_id, 'script': str(script.relative_to(REPO)),
                        'script_sha256': digest(script),
                        'positive_command': ' '.join(base), 'positive_exit_code': 0,
                        'positive_log': positive.name, 'positive_log_sha256': digest(positive),
                        'negative_command': ' '.join(negative_argv),
                        'negative_exit_code': negative_exit,
                        'negative_expected_error': 'Saved result and analysis measurement differ',
                        'negative_log': negative.name, 'negative_log_sha256': digest(negative),
                        'diagnostic_fixture': True, 'physical_acceptance_claimed': False})
    (ROOT / 'delivery-audit-proofs.json').write_text(json.dumps({
        'format': 'worker-alley-diagnostic-delivery-audit-proofs',
        'assignment_id': ASSIGNMENT, 'cases': entries}, indent=2) + '\n')
    print('Nine exact positive and tampered-source negative alley delivery audits pass')


if __name__ == '__main__':
    main()
