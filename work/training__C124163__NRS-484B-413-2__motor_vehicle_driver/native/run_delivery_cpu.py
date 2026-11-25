"""Run independent positive/negative delivery and pairwise comparison audits."""
import json
import os
from pathlib import Path
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
CONDITIONS = ('other_long', 'other_at', 'other_short',
              'district_long', 'district_at', 'district_short')

def invoke(stem, args, expected):
    output = FOLDER/(stem+'.json')
    log = FOLDER/(stem+'.log')
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO/'.runtime-work/c124163-delivery-output')
    env['TMPDIR'] = str(REPO/'.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    run = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True)
    log.write_text((run.stdout+run.stderr).rstrip()+'\n')
    if run.returncode != expected:
        raise ValueError('Delivery proof exit differs: '+stem+' '+(run.stdout+run.stderr)[-1000:])
    return output, log

def main():
    for condition in CONDITIONS:
        attempt = REPO/'.runtime-work'/f'c124163-compat-{condition}-primary-v8'
        case = AID+'__'+condition
        base = [sys.executable, str(FOLDER/'delivery_acceptance.py'),
                '--attempt', str(attempt), '--case', case]
        positive = FOLDER/f'delivery-{condition}-positive.json'
        invoke(f'delivery-{condition}-positive', base+['--diagnostic', '--output', str(positive)], 0)
        negative = FOLDER/f'delivery-{condition}-negative.json'
        _, log = invoke(f'delivery-{condition}-negative', base+['--output', str(negative)], 1)
        if 'Missing delivery source: capture-seal.json' not in log.read_text():
            raise ValueError('Synthetic-as-physical rejection differs: '+condition)
        print(json.dumps({'delivery': condition, 'positive': True, 'negative': True}), flush=True)
    pairs = [('other_long', 'other_at'), ('other_at', 'other_short'),
             ('district_long', 'district_at'), ('district_at', 'district_short')]
    for i, (first, second) in enumerate(pairs, 1):
        stem = f'comparison-{i}-audit'
        cmd = [sys.executable, str(FOLDER/'comparison_audit.py'),
               '--first', str(REPO/'.runtime-work'/f'c124163-compat-{first}-primary-v8'),
               '--second', str(REPO/'.runtime-work'/f'c124163-compat-{second}-primary-v8'),
               '--output', str(FOLDER/(stem+'.json'))]
        invoke(stem, cmd, 0)
        print(json.dumps({'comparison': i, 'passed': True}), flush=True)

if __name__ == '__main__':
    main()
