"""Lead-owned exact-case offline acceptance; fresh attempt directories only."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    batch = read(ROOT / 'batch.json')
    entries = []
    for number, aid in enumerate(batch['assignments']):
        manifest_path = ROOT / 'work' / aid / 'execution-manifest.json'
        manifest = read(manifest_path)
        for index, case in enumerate(manifest['cases']):
            output = ROOT / '.runtime-work' / ('lead-v1-%02d-%02d' % (number, index))
            if output.exists():
                raise ValueError('Retain previous lead attempt; choose a new validation prefix: ' + str(output))
            command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline', '--manifest', str(manifest_path),
                       '--case', case['case_id'], '--output', str(output)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if run.returncode:
                print(run.stdout, run.stderr, file=sys.stderr)
                raise SystemExit(run.returncode)
            log = output / 'offline.log'
            if not log.is_file():
                raise RuntimeError('Missing exact-case offline log: ' + case['case_id'])
            retained = ROOT / 'work/_shared/lead-logs' / (case['case_id'] + '.log')
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(log, retained)
            entries.append({'assignment_id': aid, 'case_id': case['case_id'], 'command': ' '.join(command),
                            'exit_code': 0, 'log': str(retained.relative_to(ROOT)), 'sha256': sha(retained)})
    acceptance = ROOT / 'work/_shared/lead-offline.json'
    acceptance.write_text(json.dumps({'format': 'lead-exact-case-offline-v1', 'cases': entries}, indent=2) + '\n')
    print(json.dumps({'assignments': len(batch['assignments']), 'exact_cases': len(entries),
                      'all_offline_passed': True, 'report': str(acceptance.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
