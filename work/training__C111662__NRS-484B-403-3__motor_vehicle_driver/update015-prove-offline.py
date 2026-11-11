"""Run all current U-turn and divided-opening CPU construction bundles."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
PROOFS = HERE / 'update015-proofs'
GROUPS = (
    ('intersection', HERE / 'native/draft-execution-manifest.json',
     ('reference', 'contrast')),
    ('divided', HERE / 'native/divided-opening/draft-execution-manifest.json',
     ('divided_reference', 'divided_opening')),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    PROOFS.mkdir(exist_ok=True)
    matrix = {'format': 'c111662-update015-offline-four-camera-v1',
              'scope': 'unselected synthetic source-shape CPU proof', 'bundles': []}
    for branch, manifest_path, cases in GROUPS:
        manifest = json.loads(manifest_path.read_text())
        for suffix in cases:
            case_id = HERE.name + '__' + suffix
            entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                label = branch + '-' + suffix + '-' + candidate
                output = REPO / '.runtime-work' / ('update015-c111662-v3-' + label)
                command = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                           '--manifest', str(manifest_path), '--case', case_id,
                           '--candidate', candidate, '--output', str(output),
                           '--python', str(PYTHON)]
                completed = subprocess.run(command, cwd=REPO, capture_output=True,
                                           text=True)
                command_log = PROOFS / (label + '-command.log')
                command_log.write_text(completed.stdout + completed.stderr)
                selected = (entry if candidate == 'primary' else next(
                    item for item in entry['candidates'] if item['id'] == candidate))
                row = {'branch': branch, 'case_id': case_id,
                       'candidate_id': candidate,
                       'construction_sha256': selected['construction_sha256'],
                       'command_log': command_log.relative_to(HERE).as_posix(),
                       'command_log_sha256': sha(command_log),
                       'exit_code': completed.returncode}
                if completed.returncode == 0:
                    log = PROOFS / (label + '-offline.log')
                    shutil.copyfile(output / 'offline.log', log)
                    row.update(offline_passed=True,
                               offline_log=log.relative_to(HERE).as_posix(),
                               offline_log_sha256=sha(log))
                    print(label, 'passed', flush=True)
                else:
                    row['error'] = (completed.stdout + completed.stderr)[-1200:]
                    print(label, 'FAILED', row['error'][-450:], flush=True)
                matrix['bundles'].append(row)
                (HERE / 'update015-offline-proof-matrix.json').write_text(
                    json.dumps(matrix, indent=2) + '\n')
    print('passed', sum(item.get('offline_passed', False)
                        for item in matrix['bundles']), '/16')


if __name__ == '__main__':
    run()
