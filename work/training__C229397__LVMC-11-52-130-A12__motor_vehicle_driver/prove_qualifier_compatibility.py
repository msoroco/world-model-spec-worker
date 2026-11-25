"""Run pinned public compatibility in an isolated scratch repository layout."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE_PACKAGE = HERE / 'qualifier-saved-package'
SCRATCH = ROOT / '.runtime-work/c229397-qualifier-compat-repo-v2'
DESTINATION = SCRATCH / 'work' / ASSIGNMENT
DECODER = ROOT / '.runtime-work/c150129-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if SCRATCH.exists():
        raise ValueError('Retain prior public qualifier compatibility scratch')
    shutil.copytree(SOURCE_PACKAGE, DESTINATION)
    for stem in ('traffic', 'law', 'officer', 'device'):
        for ending in ('.json', '-recipe.json'):
            name = 'diagnostic-qualifier-' + stem + ending
            shutil.copyfile(HERE / name, DESTINATION / name)
    results = {}
    manifest = DESTINATION / 'execution-manifest.json'
    for suffix, stem in (('traffic_conflict_near', 'traffic'),
                         ('law_compliance_near', 'law'),
                         ('police_direction_near', 'officer'),
                         ('device_direction_near', 'device')):
        case_id = ASSIGNMENT + '__' + suffix
        output = SCRATCH / '.runtime-work' / ('compat-' + stem)
        command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                   '--manifest', str(manifest), '--case', case_id,
                   '--output', str(output), '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(DECODER)]
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work')
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   capture_output=True, text=True)
        proof = HERE / 'proofs' / 'qualifiers' / stem
        proof.mkdir(parents=True, exist_ok=True)
        (proof / 'public-compatibility.log').write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise ValueError('Pinned public qualifier compatibility failed: ' +
                             completed.stderr[-1200:])
        receipt = json.loads((output / 'compatibility.json').read_text())
        if (receipt.get('passed') is not True or
                receipt.get('case_id') != case_id or
                'negative_case_source' not in receipt.get('checks', [])):
            raise ValueError('Public compatibility receipt incomplete')
        for source, target in (('compatibility.json', 'compatibility.json'),
                               ('compatibility-analysis.log', 'analysis.log'),
                               ('negative-analysis.log', 'negative.log')):
            shutil.copyfile(output / source, proof / target)
        results[suffix] = {'construction_sha256': receipt['construction_sha256'],
                           'receipt_sha256': sha(proof / 'compatibility.json'),
                           'analysis_log_sha256': sha(proof / 'analysis.log'),
                           'negative_log_sha256': sha(proof / 'negative.log'),
                           'public_command_log_sha256': sha(proof / 'public-compatibility.log')}
    print(json.dumps({'passed': True, 'diagnostic_fixture': True,
                      'cases': results, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
