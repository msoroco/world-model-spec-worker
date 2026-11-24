"""Run exact-case positive and negative CPU delivery rehearsals."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    folder = HERE / 'delivery-proof'
    folder.mkdir(exist_ok=True)
    script = HERE / 'delivery_audit.py'
    checks = ['native_source', 'all_participants', 'time_join',
              'full_video_decode', 'actual_pixels', 'physical_completion']
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        base = [sys.executable, str(script), '--case', case]
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['TMPDIR'] = str(ROOT / '.runtime-work')
        results = {}
        for mode, command in (('positive', base + ['--diagnostic']),
                              ('negative', base)):
            done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=60)
            log = folder / (suffix + '-' + mode + '.log')
            log.write_text(done.stdout.rstrip() + '\n')
            results[mode] = (done.returncode, log)
        positive, plog = results['positive']
        negative, nlog = results['negative']
        expected = 'Original Native source required for delivery acceptance'
        if positive or not negative or expected not in nlog.read_text():
            raise ValueError('Delivery rehearsal failed: ' + suffix)
        prefix = '.venv-cpu/bin/python work/' + HERE.name + '/delivery_audit.py --case ' + case
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': checks,
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': prefix + ' --diagnostic',
            'negative_command': prefix,
            'test_exit_code': 0, 'negative_exit_code': negative,
            'negative_expected_error': expected,
            'test_log': plog.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(plog),
            'negative_log': nlog.relative_to(HERE).as_posix(),
            'negative_log_sha256': sha(nlog)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_rehearsal_cases': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
