"""Rebind exact proofs after correcting the fixed lead source in ego-speed diagnostic."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
case = folder.name + '__source_verified_faster_ego'
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = next(row for row in manifest['cases'] if row['case_id'] == case)
case_folder = folder / 'cases/source_verified_faster_ego'
stem = '.runtime-work/c101303-fixed-ego-speed-v1'
validator = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    with log.open('w') as out:
        subprocess.run(args, cwd=repo, stdout=out, stderr=subprocess.STDOUT, check=True)


for label, row in [('primary', entry), *[(candidate['id'], candidate)
                                      for candidate in entry['candidates']]]:
    compatible = repo / stem / (label + '-compat')
    saved = repo / stem / (label + '-saved')
    compat_command = ['.venv-cpu/bin/python', 'runtime.py', 'compatibility',
                      '--manifest', str(manifest_path.relative_to(repo)), '--case', case,
                      '--output', str(compatible.relative_to(repo)),
                      '--library', 'runtime/library', '--validator', validator]
    if label != 'primary':
        compat_command += ['--candidate', label]
    compat_log = case_folder / (label + '-compatibility-current.log')
    if label == 'primary':
        if not compatible.is_dir() or not compat_log.is_file():
            raise ValueError('Primary positive compatibility must pass first')
    else:
        run(compat_command, compat_log)
    receipt = json.loads((compatible / 'compatibility.json').read_text())
    if receipt['passed'] is not True or receipt['candidate_id'] != label or \
            receipt['fixture_recipe_sha256'] != sha(case_folder / 'diagnostic-recipe.json'):
        raise ValueError('Current exact compatibility failed: ' + label)
    spec = row['compatibility']
    for source, target in [('compatibility.json', 'receipt'),
                           ('compatibility-analysis.log', 'log'),
                           ('negative-analysis.log', 'negative_log')]:
        shutil.copyfile(compatible / source, folder / spec[target])
    spec['sha256'] = sha(folder / spec['receipt'])
    spec['replay_command'] = ' '.join(compat_command)
    spec['replay_log'] = str(compat_log.relative_to(folder))
    spec['replay_log_sha256'] = sha(compat_log)
    save_command = ['.venv-cpu/bin/python', 'runtime.py', 'process-saved',
                    '--manifest', str(manifest_path.relative_to(repo)), '--case', case,
                    '--attempt', str(compatible.relative_to(repo)),
                    '--output', str(saved.relative_to(repo)),
                    '--library', 'runtime/library', '--validator', validator]
    save_log = case_folder / (label + '-saved-current.log')
    if label == 'primary':
        if not saved.is_dir() or not save_log.is_file():
            raise ValueError('Primary recorded-only saved processing must pass first')
    else:
        run(save_command, save_log)
    processing = saved / 'v0001/processing.json'
    if not processing.is_file():
        raise ValueError('Recorded-only processing receipt missing: ' + label)
    target = case_folder / (label + '-saved-processing.json')
    shutil.copyfile(processing, target)
    post = row.setdefault('post_capture', {})
    post.update(recorded_only=True, command=' '.join(save_command),
                test_log=str(save_log.relative_to(folder)),
                test_log_sha256=sha(save_log), test_exit_code=0,
                processing_receipt=str(target.relative_to(folder)),
                processing_sha256=sha(target))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('compatibility and recorded-only saved processing', label, flush=True)
