"""Run exact positive and negative CPU auditor proofs and bind their logs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = HERE / 'prove_delivery_acceptance.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        proofs = {}
        for mode in ('positive', 'negative'):
            command = (f'.venv-cpu/bin/python work/{HERE.name}/{script.name} '
                       f'--case {case} --mode {mode}')
            log = f'{suffix}-delivery-{mode}.log'
            with (HERE / log).open('w') as output:
                result = subprocess.run(command.split(), cwd=REPO, stdout=output,
                                        stderr=subprocess.STDOUT)
            if (mode == 'positive' and result.returncode != 0 or
                    mode == 'negative' and result.returncode == 0):
                raise ValueError(f'Unexpected {mode} auditor result: {case}')
            proofs[mode] = {'command': command, 'log': log, 'exit_code': result.returncode,
                            'log_sha256': sha(HERE / log)}
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': proofs['positive']['command'],
            'test_log': proofs['positive']['log'],
            'test_log_sha256': proofs['positive']['log_sha256'],
            'test_exit_code': proofs['positive']['exit_code'],
            'negative_command': proofs['negative']['command'],
            'negative_log': proofs['negative']['log'],
            'negative_log_sha256': proofs['negative']['log_sha256'],
            'negative_exit_code': proofs['negative']['exit_code'],
            'negative_expected_error': 'Physical completion source changed',
            'proof_scope': 'diagnostic CPU auditor boundary only; no Native physical acceptance',
        }
        validate_case(HERE, entry, ['demo-test', 'full-test'])
        print(case + ': diagnostic auditor positive and negative CPU proofs passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
