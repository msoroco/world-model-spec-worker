"""Run all eight unselected exact v1 package positives and source negatives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    env = dict(os.environ)
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    records = []
    for suffix in ('exception_1_1', 'exception_1_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            log = HERE / ('exception-package-' + suffix + '-' + candidate + '.log')
            command = [sys.executable, str(HERE / 'probe-package-exception.py'),
                       '--suffix', suffix, '--candidate', candidate]
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=ROOT, env=env,
                                           stdout=stream, stderr=subprocess.STDOUT, timeout=600)
            if completed.returncode:
                raise RuntimeError('Exact steady package failed: ' + str(log))
            receipt = json.loads(log.read_text().splitlines()[-1])
            if receipt['positive']['passed'] is not True or receipt['negative']['exit_code'] == 0:
                raise RuntimeError('Countdown package receipt did not prove positive and negative')
            records.append({'case_suffix': suffix, 'candidate': candidate,
                            'case_id': receipt['positive']['case_id'],
                            'construction_sha256': receipt['positive']['construction_sha256'],
                            'runtime_manifest_sha256': receipt['positive']['runtime_manifest_sha256'],
                            'fixture_sha256': receipt['positive']['fixture_sha256'],
                            'package_log': log.name, 'package_log_sha256': sha(log),
                            'retained_scratch': receipt['scratch'],
                            'scope': receipt['scope']})
            print(suffix, candidate, 'positive and negative pass', flush=True)
    summary = {'format': 'c10316-unselected-exception-v1-package-summary',
               'records': records, 'selected_cases': 0, 'accepted_recordings': 0}
    (HERE / 'draft-package-exception-summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
