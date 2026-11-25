"""Refresh exact-case synthetic physical/lifecycle proofs in ignored work root."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    environment = dict(os.environ,
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c111278-owner/pipeline'),
        PYTHONDONTWRITEBYTECODE='1',
        TMPDIR=str(REPO / '.runtime-work/c111278-owner/tmp'),
        PYTHONPATH=str(REPO / 'runtime/scenario_pipeline') + ':' +
                   str(REPO / 'runtime/python'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        output = REPO / '.runtime-work/c111278-owner' / ('physical-' + suffix)
        if output.exists():
            shutil.rmtree(output)
        command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'physical_probe.py'),
                   '--case', entry['case_id'], '--output', str(output)]
        run = subprocess.run(command, cwd=REPO, env=environment, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = ROOT / ('physical-' + suffix + '-probe.log')
        log.write_text('\n'.join(line.rstrip() for line in run.stdout.splitlines()).rstrip() + '\n')
        if run.returncode:
            raise RuntimeError(suffix + ': ' + run.stdout[-1500:])
        proof = {'construction_sha256': entry['construction_sha256'],
                 'fixtures': [],
                 'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                     'restoration_verified', 'native_exit', 'owner_released',
                     'saved_processing_started'], 'exit_code': 0,
                     'log': log.name, 'log_sha256': sha(log)},
                 'scope': 'Synthetic intersection travel and lifecycle protocol only; no Native capture'}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = ROOT / ('physical-' + suffix + '-' + kind + '.json')
            proof['fixtures'].append({'kind': kind,
                'command': ' '.join(command), 'exit_code': 0,
                'log': log.name, 'log_sha256': sha(log),
                'result': result.name, 'result_sha256': sha(result)})
        receipt = ROOT / ('physical-' + suffix + '-proof.json')
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': receipt.name,
                                         'sha256': sha(receipt)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
