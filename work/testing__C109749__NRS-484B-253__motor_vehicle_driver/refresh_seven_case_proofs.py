"""Rebind exact CPU processing after the canonical seven-case integration.

Fresh ignored attempt roots avoid overwriting retained originals. This script
does not run Native simulation or make a physical acceptance claim.
"""
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as output:
        subprocess.run(args, cwd=repo, stdout=output, stderr=subprocess.STDOUT, check=True)


manifest = json.loads(manifest_path.read_text())
supported = [entry['case_id'] for entry in manifest['cases']]
first = manifest['cases'][0]
root_config = json.loads((folder / 'config.json').read_text())
root_config['supported_case_ids'] = supported
write(folder / 'config.json', root_config)
for item in [first, *first['candidates']]:
    path = folder / item['construction']
    bundle = json.loads(path.read_text())
    for file in bundle['files']:
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['supported_case_ids'] = supported
            file['content'] = json.dumps(config, indent=2) + '\n'
    write(path, bundle)
    item['construction_sha256'] = sha(path)
write(manifest_path, manifest)

for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    for label, item in [('primary', entry), *[(row['id'], row) for row in entry['candidates']]]:
        output = f'.runtime-work/c109749-seven-case-{suffix}-{label}-offline-v1'
        command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                   '--manifest', str(manifest_path.relative_to(repo)),
                   '--case', entry['case_id'], '--output', output]
        if label != 'primary':
            command += ['--candidate', label]
        offline = item['offline']
        run(command, folder / offline['log'])
        offline.update(command=shlex.join(command), exit_code=0,
                       construction_sha256=item['construction_sha256'],
                       log_sha256=sha(folder / offline['log']))
        print('offline', suffix, label, flush=True)
write(manifest_path, manifest)

for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    for label, item in [('primary', entry), *[(row['id'], row) for row in entry['candidates']]]:
        prefix = f'.runtime-work/c109749-seven-case-{suffix}-{label}'
        compat = prefix + '-compat-v1'
        saved = prefix + '-saved-v1'
        command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'compatibility',
                   '--manifest', str(manifest_path.relative_to(repo)),
                   '--case', entry['case_id'], '--output', compat,
                   '--library', 'runtime/library',
                   '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        if label != 'primary':
            command += ['--candidate', label]
        spec = item['compatibility']
        run(command, folder / spec['replay_log'])
        for source, destination in [('compatibility.json', spec['receipt']),
                                    ('compatibility-analysis.log', spec['log']),
                                    ('negative-analysis.log', spec['negative_log'])]:
            shutil.copyfile(repo / compat / source, folder / destination)
        saved_command = [str(repo / '.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
                         '--manifest', str(manifest_path.relative_to(repo)),
                         '--case', entry['case_id'], '--attempt', compat,
                         '--output', saved, '--library', 'runtime/library',
                         '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        post = item['post_capture']
        run(saved_command, folder / post['test_log'])
        if label == 'primary':
            receipt = repo / saved / 'v0001/processing.json'
            if suffix == 'reciprocal_yield_after_turn':
                shutil.copyfile(receipt, folder / 'primary-saved-processing.json')
            elif suffix == 'reciprocal_continues_after_turn':
                shutil.copyfile(receipt, folder / 'cases/reciprocal_continues/primary-saved-processing.json')
            else:
                shutil.copyfile(receipt, folder / 'cases' / suffix / 'proofs/primary/processing.json')
        spec['sha256'] = sha(folder / spec['receipt'])
        spec['replay_command'] = shlex.join(command)
        post.update(command=shlex.join(saved_command), feedback_command=f'cat {saved}/v0001/feedback.json',
                    test_exit_code=0, test_log_sha256=sha(folder / post['test_log']))
        print('compatibility and saved', suffix, label, flush=True)
write(manifest_path, manifest)
print(json.dumps({'cases': len(manifest['cases']), 'candidate_proofs': 4*len(manifest['cases']),
                  'status': 'exact seven-case CPU processing rebound; physical and delivery fixture refresh pending'}))
