"""Bind mock-only original delivery audit contract proofs to the draft preview."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
SCRIPT = FOLDER / 'native/prove_original_delivery_contract.py'
PREVIEW = FOLDER / 'execution-manifest-proof-bound-preview.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, expected):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode != expected:
        raise RuntimeError(f'{log.name}: exit {result.returncode}, expected {expected}')
    return result.returncode


def main():
    manifest = json.loads(PREVIEW.read_text())
    python = ROOT / '.venv-cpu/bin/python'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        positive = FOLDER / f'update064-{suffix}-original-contract.log'
        negative = FOLDER / f'update064-{suffix}-original-contract-negative.log'
        base = [str(python), str(SCRIPT), '--case', case]
        run(base, positive, 0)
        run(base + ['--negative'], negative, 2)
        proof = json.loads(positive.read_text())
        assert proof['mock_only'] and not proof['original_native_observed']
        assert not proof['delivery_acceptance_claimed']
        assert len(proof['negative_rejections']) == 8
        relscript = SCRIPT.relative_to(FOLDER).as_posix()
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': proof['contract_checks'],
            'script': relscript, 'script_sha256': sha(SCRIPT),
            'command': '.venv-cpu/bin/python work/' + FOLDER.name + '/' + relscript + ' --case ' + case,
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': '.venv-cpu/bin/python work/' + FOLDER.name + '/' + relscript + ' --case ' + case + ' --negative',
            'negative_exit_code': 2, 'negative_log': negative.name,
            'negative_log_sha256': sha(negative),
            'negative_expected_error': 'EXPECTED CPU MOCK REJECTION: Original delivery sources changed',
            'proof_scope': 'mocked_original_branch_contract_only',
            'original_native_observed': False,
            'delivery_acceptance_claimed': False,
        }
    PREVIEW.write_text(json.dumps(manifest, indent=2) + '\n')
    sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
    from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
    for entry in manifest['cases']:
        validate_case(FOLDER, entry, expected_sets=['full-train'])
    print(json.dumps({'cases': [e['case_id'] for e in manifest['cases']],
                      'preview_sha256': sha(PREVIEW), 'mock_only': True,
                      'original_native_observed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
