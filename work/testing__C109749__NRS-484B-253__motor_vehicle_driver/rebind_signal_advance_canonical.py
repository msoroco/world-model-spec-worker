"""Replay changed root and new matched signal cases against canonical manifest."""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def run(command, log):
    log = folder / log
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as output:
        subprocess.run(command, cwd=repo, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


manifest = json.loads(manifest_path.read_text())
selected = [manifest['cases'][0], *[x for x in manifest['cases']
                                    if x['case_id'].endswith(('__signal_advance_100_at',
                                                              '__signal_advance_100_omitted'))]]
if len(selected) != 3 or len(manifest['cases']) != 11:
    raise ValueError('Expected changed root and two new exact cases')

for entry in selected:
    suffix = entry['case_id'].split('__')[-1]
    for label, item in [('primary', entry),
                        *[(candidate['id'], candidate) for candidate in entry['candidates']]]:
        if sha(folder / item['construction']) != item['construction_sha256']:
            raise ValueError('Changed construction needs a current SHA: ' + suffix + '/' + label)
        output = f'.runtime-work/c109749-eleven-case-{suffix}-{label}-offline-v1'
        command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                   '--manifest', str(manifest_path.relative_to(repo)),
                   '--case', entry['case_id'], '--output', output]
        if label != 'primary':
            command += ['--candidate', label]
        spec = item['offline']
        run(command, spec['log'])
        spec.update(command=shlex.join(command), exit_code=0,
                    construction_sha256=item['construction_sha256'],
                    log_sha256=sha(folder / spec['log']))
        print('offline', suffix, label, flush=True)
write(manifest_path, manifest)

for entry in selected:
    suffix = entry['case_id'].split('__')[-1]
    for label, item in [('primary', entry),
                        *[(candidate['id'], candidate) for candidate in entry['candidates']]]:
        stem = f'.runtime-work/c109749-eleven-case-{suffix}-{label}'
        compatibility_root = stem + '-compat-v1'
        saved_root = stem + '-saved-v1'
        command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'compatibility',
                   '--manifest', str(manifest_path.relative_to(repo)),
                   '--case', entry['case_id'], '--output', compatibility_root,
                   '--library', 'runtime/library',
                   '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        if label != 'primary':
            command += ['--candidate', label]
        spec = item['compatibility']
        run(command, spec['replay_log'])
        for source, target in (('compatibility.json', spec['receipt']),
                               ('compatibility-analysis.log', spec['log']),
                               ('negative-analysis.log', spec['negative_log'])):
            destination = folder / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / compatibility_root / source, destination)
        spec['sha256'] = sha(folder / spec['receipt'])
        spec['replay_command'] = shlex.join(command)
        saved_command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
                         '--manifest', str(manifest_path.relative_to(repo)),
                         '--case', entry['case_id'], '--attempt', compatibility_root,
                         '--output', saved_root, '--library', 'runtime/library',
                         '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        post = item['post_capture']
        run(saved_command, post['test_log'])
        target = (folder / ('proofs/primary/processing.json' if entry is manifest['cases'][0] and label == 'primary'
                            else f'cases/{suffix}/proofs/{label}/processing.json'))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / saved_root / 'v0001/processing.json', target)
        if entry is manifest['cases'][0] and label == 'primary':
            shutil.copyfile(target, folder / 'primary-saved-processing.json')
        post.update(command=shlex.join(saved_command),
                    feedback_command=f'cat {saved_root}/v0001/feedback.json',
                    test_exit_code=0, test_log_sha256=sha(folder / post['test_log']))
        print('compatibility and saved', suffix, label, flush=True)
    write(manifest_path, manifest)
print(json.dumps({'canonical_cases': len(manifest['cases']),
                  'replayed_candidates': 12, 'recorded_only': True,
                  'physical_acceptance_claimed': False}))
