"""Construct and prove one exact route-selection fallback at a time.

Diagnostic compatibility remains synthetic. The trigger is an observable Native
route-selection failure to review before choosing this candidate in a real run.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'execution-manifest.json'
PYTHON = ROOT/'.venv-cpu/bin/python'
VALIDATOR = ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'

OPTIONS = {
    'fallback1': {
        'replacement': 'spacing_m=1.0, approach_steps=6',
        'trigger': {'source': 'Native marked-lane waypoint inventory',
                    'metric': 'eligible marked approach at 2 m sampling',
                    'failure_condition': 'primary 2 m sampling misses a short marked approach'},
        'changed_knobs': ['waypoint spacing 2.0 m -> 1.0 m']},
    'fallback2': {
        'replacement': 'approach_steps=4',
        'trigger': {'source': 'Native marked-lane waypoint continuity',
                    'metric': 'continuous marked approach length',
                    'failure_condition': 'primary six-step approach does not fit the marked segment'},
        'changed_knobs': ['approach steps 6 -> 4']},
    'fallback3': {
        'replacement': 'approach_steps=6, candidate_index=1',
        'trigger': {'source': 'Native spawn/topology and four-camera preview for first candidate',
                    'metric': 'first candidate spawn and camera sight-line suitability',
                    'failure_condition': 'first candidate is physically obstructed or cannot spawn while a second connected marked candidate exists'},
        'changed_knobs': ['sorted route candidate index 0 -> 1']},
}


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def prove(case_suffix, fallback, *, version=1):
    if fallback not in OPTIONS or version < 1:
        raise ValueError('Unknown fallback or version')
    data = json.loads(MANIFEST.read_text())
    case = next(x for x in data['cases'] if x['case_id'].endswith('__'+case_suffix))
    source = json.loads((HERE/case['construction']).read_text())
    entrypoint = source['entrypoint']
    old = "approach_steps=6)"
    changed = 0
    for item in source['files']:
        if item['path'] == entrypoint:
            if item['content'].count(old) != 1:
                raise ValueError('Expected one exact Native route selector call')
            item['content'] = item['content'].replace(
                old, OPTIONS[fallback]['replacement']+')')
            changed += 1
    if changed != 1:
        raise ValueError('Native runner source missing')
    source['mechanisms']['route'] = ('Original marked center/outer connected route with '
                                     + OPTIONS[fallback]['replacement'])
    source['mechanisms']['construction_status'] = fallback+'_exact_cpu_proof_pending'
    name = f'construction-{case_suffix}-{fallback}.json'
    construction = HERE/name
    write(construction, source)
    row = {'id': fallback, 'construction': name,
           'construction_sha256': sha(construction),
           'trigger': OPTIONS[fallback]['trigger'],
           'changed_knobs': OPTIONS[fallback]['changed_knobs']}
    case['candidates'] = [x for x in case['candidates'] if x['id'] != fallback]
    case['candidates'].append(row)
    write(MANIFEST, data)
    stem = f'{case_suffix}-{fallback}'
    output = ROOT/f'.runtime-work/c374648-{stem}-v{version}'
    offline_output = output/'offline'
    compat_output = output/'compatibility'
    offline_cmd = [str(PYTHON), str(ROOT/'runtime.py'), 'offline',
                   '--manifest', str(MANIFEST), '--case', case['case_id'],
                   '--candidate', fallback, '--output', str(offline_output)]
    offline_log = HERE/(stem+'-offline.log')
    with offline_log.open('w') as log:
        subprocess.run(offline_cmd, cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    compat_cmd = [str(PYTHON), str(ROOT/'runtime.py'), 'compatibility',
                  '--manifest', str(MANIFEST), '--case', case['case_id'],
                  '--candidate', fallback, '--output', str(compat_output),
                  '--library', str(ROOT/'runtime/library'),
                  '--validator', str(VALIDATOR)]
    with (HERE/(stem+'-compatibility.log')).open('w') as log:
        subprocess.run(compat_cmd, cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    for source_name, returned in [('compatibility.json', stem+'-compatibility.json'),
                                  ('compatibility-analysis.log', stem+'-compat-analysis.log'),
                                  ('negative-analysis.log', stem+'-negative.log')]:
        shutil.copy2(compat_output/source_name, HERE/returned)
    data = json.loads(MANIFEST.read_text())
    case = next(x for x in data['cases'] if x['case_id'].endswith('__'+case_suffix))
    row = next(x for x in case['candidates'] if x['id'] == fallback)
    row['offline'] = {'command': ' '.join(offline_cmd), 'exit_code': 0,
                      'log': offline_log.name, 'log_sha256': sha(offline_log),
                      'construction_sha256': row['construction_sha256']}
    row['compatibility'] = {'receipt': stem+'-compatibility.json',
                            'sha256': sha(HERE/(stem+'-compatibility.json')),
                            'log': stem+'-compat-analysis.log',
                            'negative_log': stem+'-negative.log'}
    write(MANIFEST, data)
    return {'case': case['case_id'], 'fallback': fallback,
            'construction_sha256': row['construction_sha256'],
            'manifest_sha256': sha(MANIFEST)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fallback', choices=sorted(OPTIONS), required=True)
    parser.add_argument('--version', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.fallback, version=args.version)))
