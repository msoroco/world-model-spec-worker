"""Run and bind exact-case positive/negative CPU delivery-boundary proofs."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = 'prove_delivery_acceptance.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.rsplit('__', 1)[-1]
        commands = {}
        for mode in ('positive', 'negative'):
            argv = ['.venv-cpu/bin/python', str((HERE / SCRIPT).relative_to(REPO)),
                    '--case', case, '--mode', mode]
            log = HERE / f'{short}-delivery-{mode}-v1.log'
            run = subprocess.run(argv, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(run.stdout)
            if (mode == 'positive' and run.returncode != 0) or (mode == 'negative' and
                    (run.returncode == 0 or 'Physical completion source changed' not in run.stdout)):
                raise ValueError(f'Delivery {mode} proof failed: {case}: {run.stdout}')
            commands[mode] = (argv, log, run.returncode)
        positive, negative = commands['positive'], commands['negative']
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-test', 'full-test'], 'checks': CHECKS,
            'script': SCRIPT, 'script_sha256': sha(HERE / SCRIPT),
            'command': ' '.join(positive[0]), 'test_log': positive[1].name,
            'test_log_sha256': sha(positive[1]), 'test_exit_code': positive[2],
            'negative_command': ' '.join(negative[0]),
            'negative_log': negative[1].name,
            'negative_log_sha256': sha(negative[1]),
            'negative_exit_code': negative[2],
            'negative_expected_error': 'Physical completion source changed',
            'proof_scope': 'Diagnostic CPU auditor boundary only; independent Native and pixel review pending',
        }
        print(case)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'delivery_acceptance_contracts': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
