"""Bind recorded-only processing for the 21 current fallback compatibility attempts."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
validator = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for entry in manifest['cases']:
    label = entry['case_id'].rsplit('source_verified_', 1)[1]
    for candidate in entry['candidates']:
        if candidate.get('post_capture'):
            continue
        name = candidate['id']
        source = repo / '.runtime-work/c101303-fallback-saved-v2' / (label + '-' + name + '-compat')
        case_folder = folder / ('cases/source_verified_' + label) if label != 'base' else folder
        compat_command = ['.venv-cpu/bin/python', 'runtime.py', 'compatibility',
                          '--manifest', str(manifest_path.relative_to(repo)),
                          '--case', entry['case_id'], '--candidate', name,
                          '--output', str(source.relative_to(repo)),
                          '--library', 'runtime/library', '--validator', validator]
        compat_log = case_folder / (name + '-compatibility-current.log')
        with compat_log.open('w') as stream:
            subprocess.run(compat_command, cwd=repo, stdout=stream, stderr=subprocess.STDOUT, check=True)
        receipt_path = source / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        if receipt['passed'] is not True or receipt['case_id'] != entry['case_id'] or \
                receipt['candidate_id'] != name or \
                receipt['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError('Fallback compatibility does not match construction: ' + label + '/' + name)
        output = repo / '.runtime-work/c101303-fallback-saved-v2' / (label + '-' + name + '-saved')
        command = ['.venv-cpu/bin/python', 'runtime.py', 'process-saved',
                   '--manifest', str(manifest_path.relative_to(repo)),
                   '--case', entry['case_id'],
                   '--attempt', str(source.relative_to(repo)),
                   '--output', str(output.relative_to(repo)),
                   '--library', 'runtime/library', '--validator', validator]
        log = case_folder / (name + '-recorded-only.log')
        with log.open('w') as stream:
            subprocess.run(command, cwd=repo, stdout=stream, stderr=subprocess.STDOUT, check=True)
        processing = output / 'v0001/processing.json'
        if not processing.is_file():
            raise ValueError('Saved processing receipt missing: ' + label + '/' + name)
        proof = json.loads(processing.read_text())
        if proof.get('passed') is not True or proof.get('recorded_only') is not True or \
                proof.get('originals_preserved') is not True or proof.get('candidate_id') != name or \
                proof.get('physical_acceptance_claimed') is not False:
            raise ValueError('Recorded-only fallback proof failed: ' + label + '/' + name)
        retained = case_folder / (name + '-saved-processing.json')
        shutil.copyfile(processing, retained)
        compat = candidate['compatibility']
        for source_name, key in [('compatibility.json', 'receipt'),
                                 ('compatibility-analysis.log', 'log'),
                                 ('negative-analysis.log', 'negative_log')]:
            shutil.copyfile(source / source_name, folder / compat[key])
        compat['sha256'] = sha(folder / compat['receipt'])
        compat['replay_command'] = ' '.join(compat_command)
        compat['replay_log'] = str(compat_log.relative_to(folder))
        compat['replay_log_sha256'] = sha(compat_log)
        candidate['post_capture'] = {
            'recorded_only': True,
            'command': ' '.join(command),
            'test_log': str(log.relative_to(folder)),
            'test_log_sha256': sha(log),
            'test_exit_code': 0,
            'processing_receipt': str(retained.relative_to(folder)),
            'processing_sha256': sha(retained),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print('saved', label, name, flush=True)
