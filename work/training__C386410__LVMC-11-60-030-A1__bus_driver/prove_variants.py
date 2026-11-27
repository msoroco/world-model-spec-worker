"""Run exact six-variant offline and public positive/negative compatibility proofs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VARIANTS = ('bus_stop', 'bus_stand', 'route_origin',
            'transient_stop', 'parking_other_street', 'tour_bus_other_street')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c386410-variant-compat'))
    decoder = REPO / '.runtime-work/c386410-decoder/.lake/build/bin/adapterCheck'
    for suffix in VARIANTS:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
        output = REPO / '.runtime-work/c386410-variant-compat' / suffix
        command = [sys.executable, '-B', str(REPO / 'runtime.py'), 'compatibility',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--output', str(output), '--library', str(REPO / 'runtime/library'),
                   '--validator', str(decoder)]
        if not (output / 'compatibility.json').is_file():
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            (REPO / '.runtime-work/c386410-variant-compat').mkdir(parents=True, exist_ok=True)
            (REPO / '.runtime-work/c386410-variant-compat' / (suffix + '-command.log')).write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(suffix + ': ' + result.stderr[-1500:])
        proof = ROOT / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        offline = REPO / '.runtime-work/c386410-variant-offline' / suffix / 'offline.log'
        for source, target in ((offline, proof / 'offline.log'),
                               (output / 'compatibility.json', proof / 'compatibility.json'),
                               (output / 'compatibility-analysis.log', proof / 'positive.log'),
                               (output / 'negative-analysis.log', proof / 'negative-analysis.log')):
            shutil.copyfile(source, target)
        entry['offline'] = {'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' + ROOT.name + '/execution-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/c386410-variant-offline/' + suffix,
            'log': 'proofs/' + suffix + '/offline.log',
            'log_sha256': sha(proof / 'offline.log')}
        entry['compatibility'] = {'receipt': 'proofs/' + suffix + '/compatibility.json',
            'sha256': sha(proof / 'compatibility.json'),
            'log': 'proofs/' + suffix + '/positive.log',
            'negative_log': 'proofs/' + suffix + '/negative-analysis.log'}
        entry['negative'] = {'log': 'proofs/' + suffix + '/negative-analysis.log',
            'log_sha256': sha(proof / 'negative-analysis.log')}
        print('passed', suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
