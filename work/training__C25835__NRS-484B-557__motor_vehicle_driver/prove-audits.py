"""Exercise independent diagnostic audits and explicit source-removal negatives."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
PYTHON = sys.executable


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(tokens, log):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    (ROOT / '.runtime-work/c25835-owner/audits').mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        proof = HERE / 'proofs' / suffix
        attempt = ROOT / '.runtime-work/c25835-owner/public' / (suffix + '-primary-v1')
        processing = ROOT / '.runtime-work/c25835-owner/saved' / ('output-' + suffix + '-v1') / 'v0001/processing.json'
        base = [PYTHON, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(attempt), '--processing', str(processing),
                '--output', str(ROOT / '.runtime-work/c25835-owner/audits' / ('delivery-' + suffix + '-positive.json')),
                '--diagnostic']
        positive = proof / 'delivery-positive.log'
        negative = proof / 'delivery-negative.log'
        positive_exit = run(base, positive)
        negative_tokens = base + ['--omit-source', 'designation-authority.txt']
        negative_exit = run(negative_tokens, negative)
        if positive_exit != 0 or negative_exit == 0 or 'Missing source: designation-authority.txt' not in negative.read_text():
            raise ValueError('Delivery audit positive/negative proof failed: ' + case)
        entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion', 'separate_designation_sign_and_occluder_review'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(base), 'test_exit_code': positive_exit,
            'test_log': str(positive.relative_to(HERE)), 'test_log_sha256': sha(positive),
            'negative_command': ' '.join(negative_tokens), 'negative_exit_code': negative_exit,
            'negative_expected_error': 'Missing source: designation-authority.txt',
            'negative_log': str(negative.relative_to(HERE)), 'negative_log_sha256': sha(negative)}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison_script = HERE / 'comparison_audit.py'
    for comparison in plan['comparisons']:
        ident = comparison['comparison_id']
        token = ident.split('__')[-1]
        command = [PYTHON, str(comparison_script), '--comparison', ident]
        for case in comparison['case_ids']:
            suffix = case.split('__')[-1]
            processing = ROOT / '.runtime-work/c25835-owner/saved' / ('output-' + suffix + '-v1') / 'v0001/processing.json'
            command += ['--processing', case + '=' + str(processing)]
        command += ['--output', str(ROOT / '.runtime-work/c25835-owner/audits' / ('comparison-' + token + '.json'))]
        positive = HERE / 'proofs' / ('comparison-' + token + '-positive.log')
        negative = HERE / 'proofs' / ('comparison-' + token + '-negative.log')
        positive_exit = run(command, positive)
        negative_tokens = command + ['--omit-case', comparison['case_ids'][-1]]
        negative_exit = run(negative_tokens, negative)
        if positive_exit != 0 or negative_exit == 0 or 'Missing comparison case' not in negative.read_text():
            raise ValueError('Comparison audit positive/negative proof failed: ' + ident)
        comparison['audit'] = {'script': 'comparison_audit.py', 'script_sha256': sha(comparison_script),
            'command': ' '.join(command), 'test_log': str(positive.relative_to(HERE)),
            'test_log_sha256': sha(positive), 'test_exit_code': positive_exit,
            'negative_command': ' '.join(negative_tokens), 'negative_log': str(negative.relative_to(HERE)),
            'negative_log_sha256': sha(negative), 'negative_exit_code': negative_exit}
    (HERE / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print({'delivery_audits': len(manifest['cases']), 'comparisons': len(plan['comparisons'])})


if __name__ == '__main__':
    main()
