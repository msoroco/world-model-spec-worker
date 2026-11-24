"""Dispatch one reviewed exact C125751 bundle through the pinned runtime."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def check():
    config = json.loads((ROOT/'config.json').read_text())
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    ids = [case['case_id'] for case in manifest['cases']]
    if ids != config['supported_case_ids'] or config['assignment_id'] != manifest['assignment_id']:
        raise ValueError('exact selected delivery identities differ')
    if len(config['cameras']) != 4 or config['duration_s'] != 45:
        raise ValueError('four-view duration contract differs')
    return ids

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--output')
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--python')
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    cases = check()
    if args.check:
        print('exact C125751 selected bundles:', ','.join(cases))
        return
    if args.case not in cases or not all((args.output, args.host, args.port, args.python)):
        raise ValueError('select one exact case and supply the Native handoff')
    command = [args.python, str(REPO/'runtime.py'), 'capture', '--manifest',
               str(ROOT/'execution-manifest.json'), '--case', args.case,
               '--output', args.output, '--host', args.host, '--port', args.port,
               '--python', args.python, '--candidate', args.candidate]
    subprocess.run(command, check=True)

if __name__ == '__main__':
    main()
