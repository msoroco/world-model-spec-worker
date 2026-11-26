"""Run and bind exact positive/negative compatibility diagnostics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-route-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c230259_627_decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest(entry, candidate, output, command):
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    label = suffix + '-' + candidate
    target = HERE / 'compatibility'
    target.mkdir(exist_ok=True)
    paths = {}
    for source, dest in (('compatibility.json', label + '-compatibility.json'),
                         ('compatibility-analysis.log', label + '-compatibility-analysis.log'),
                         ('negative-analysis.log', label + '-negative-analysis.log')):
        source_path = output / source
        destination = target / dest
        if not source_path.is_file():
            raise ValueError('Compatibility output missing: ' + source)
        if source_path.read_bytes().endswith(b'\n\n'):
            raise ValueError('Compatibility output has blank EOF: ' + source)
        shutil.copyfile(source_path, destination)
        paths[source] = destination
    receipt = json.loads(paths['compatibility.json'].read_text())
    source = entry if candidate == 'primary' else entry['candidates'][0]
    if not receipt.get('passed') or receipt['case_id'] != entry['case_id'] \
            or receipt['candidate_id'] != candidate \
            or receipt['construction_sha256'] != source['construction_sha256']:
        raise ValueError('Compatibility receipt selected another construction')
    if receipt['log_sha256'] != sha(paths['compatibility-analysis.log']) \
            or receipt['negative_log_sha256'] != sha(paths['negative-analysis.log']):
        raise ValueError('Compatibility receipt log hashes differ')
    source['compatibility'] = {'receipt': str(paths['compatibility.json'].relative_to(HERE)),
        'sha256': sha(paths['compatibility.json']),
        'log': str(paths['compatibility-analysis.log'].relative_to(HERE)),
        'negative_log': str(paths['negative-analysis.log'].relative_to(HERE)),
        'command': ' '.join(command)}
    if candidate == 'primary':
        entry['negative'] = {'log': source['compatibility']['negative_log']}
    return {'case_id': entry['case_id'], 'candidate': candidate,
            'receipt_sha256': source['compatibility']['sha256']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=['witness_1', 'witness_2',
                        'exception_1_1', 'exception_1_2'])
    parser.add_argument('--candidate', choices=['primary', 'fallback1'])
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c230259_627_runtime')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if args.suffix and args.suffix != suffix:
            continue
        for candidate in ('primary', 'fallback1'):
            if args.candidate and args.candidate != candidate:
                continue
            if suffix == 'witness_1' and candidate == 'primary':
                output = ROOT / '.runtime-work/c230259_627_witness1_primary_compat_v4'
            else:
                output = ROOT / '.runtime-work' / ('c230259_627_' + suffix + '_' + candidate + '_compat_v1')
            command = ['.venv-cpu/bin/python', '-B', 'runtime.py', 'compatibility',
                '--manifest', str(MANIFEST.relative_to(ROOT)), '--case', entry['case_id'],
                '--candidate', candidate, '--output', str(output.relative_to(ROOT)),
                '--library', 'runtime/library',
                '--validator', str(VALIDATOR.relative_to(ROOT))]
            if not (output / 'compatibility.json').is_file():
                if output.exists():
                    raise ValueError('Retain failed output and choose a new version: ' + str(output))
                log = ROOT / '.runtime-work' / ('c230259_627_' + suffix + '_' + candidate + '_command.log')
                with log.open('w') as stream:
                    completed = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                               stderr=subprocess.STDOUT, timeout=600)
                if completed.returncode:
                    raise RuntimeError('Compatibility failed: ' + str(log))
            print(json.dumps(ingest(entry, candidate, output, command)), flush=True)
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
