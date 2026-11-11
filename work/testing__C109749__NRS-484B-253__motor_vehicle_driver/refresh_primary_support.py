"""Refresh the first exact case after adding a supported comparison case.

This is a reproducible CPU proof repair. It never launches CARLA.
"""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder/'execution-manifest.json'


def read(path): return json.loads(path.read_text())
def write(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as out:
        subprocess.run(args, cwd=repo, stdout=out, stderr=subprocess.STDOUT, check=True)


def repair():
    manifest = read(manifest_path)
    first, second = manifest['cases'][:2]
    case = first['case_id']
    supported = [case, second['case_id']]
    root_config = read(folder/'config.json')
    root_config['supported_case_ids'] = supported
    write(folder/'config.json', root_config)
    selections = [('primary', first)] + [(x['id'], x) for x in first['candidates']]
    for candidate, item in selections:
        path = folder/item['construction']
        construction = read(path)
        for file in construction['files']:
            if file['path']=='config.json':
                config = json.loads(file['content'])
                config['supported_case_ids'] = supported
                file['content'] = json.dumps(config, indent=2)+'\n'
        write(path, construction)
        item['construction_sha256'] = sha(path)
        print('updated', candidate, item['construction_sha256'], flush=True)
    write(manifest_path, manifest)

    for candidate, item in selections:
        output = repo/'.runtime-work'/f'c109749-root-support-{candidate}-offline-v1'
        args = shlex.split(item['offline']['command'])
        args[args.index('--output')+1] = str(output.relative_to(repo))
        log = folder/item['offline']['log']
        run(args, log)
        item['offline']['command'] = shlex.join(args)
        item['offline']['construction_sha256'] = item['construction_sha256']
        item['offline']['log_sha256'] = sha(log)
        print('offline passed', candidate, flush=True)
    write(manifest_path, manifest)

    # Freeze the manifest through all compatibility/saved-processing pairs.
    # Candidate-selection receipts bind its exact hash.
    proofs=[]
    for candidate, item in selections:
        label = f'c109749-root-support-{candidate}'
        compat = repo/'.runtime-work'/(label+'-compat-v1')
        saved = repo/'.runtime-work'/(label+'-saved-v1')
        args = [str(repo/'.venv-cpu/bin/python'), 'runtime.py', 'compatibility',
                '--manifest', str(manifest_path.relative_to(repo)), '--case', case,
                '--output', str(compat.relative_to(repo)), '--library', 'runtime/library',
                '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        if candidate!='primary': args += ['--candidate', candidate]
        cli_log = folder/('primary-compatibility.log' if candidate=='primary' else f'cases/{candidate}-compatibility.log')
        run(args, cli_log)
        spec = item['compatibility']
        shutil.copyfile(compat/'compatibility.json', folder/spec['receipt'])
        shutil.copyfile(compat/'compatibility-analysis.log', folder/spec['log'])
        shutil.copyfile(compat/'negative-analysis.log', folder/spec['negative_log'])
        saved_args = [str(repo/'.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
                      '--manifest', str(manifest_path.relative_to(repo)), '--case', case,
                      '--attempt', str(compat.relative_to(repo)), '--output', str(saved.relative_to(repo)),
                      '--library', 'runtime/library',
                      '--validator', '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        saved_log = folder/item['post_capture']['test_log']
        run(saved_args, saved_log)
        if candidate=='primary':
            shutil.copyfile(saved/'v0001/processing.json', folder/'primary-saved-processing.json')
        proofs.append((candidate,item,shlex.join(saved_args),saved_log))
        print('compatibility and saved passed',candidate,flush=True)
    for candidate,item,saved_command,saved_log in proofs:
        item['compatibility']['sha256'] = sha(folder/item['compatibility']['receipt'])
        item['post_capture']['command'] = saved_command
        item['post_capture']['test_log_sha256'] = sha(saved_log)
        item['post_capture']['feedback_command'] = 'cat .runtime-work/c109749-root-support-'+candidate+'-saved-v1/v0001/feedback.json'
    write(manifest_path, manifest)
    print('all four exact candidates rebound', flush=True)


if __name__=='__main__': repair()
