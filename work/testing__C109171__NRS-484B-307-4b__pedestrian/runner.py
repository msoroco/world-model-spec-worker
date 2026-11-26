"""Dispatch an exact selected pedestrian case through the pinned runtime capture."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    if args.case not in config['supported_case_ids']:
        raise ValueError('Unknown exact C109171 case')
    if args.check:
        print('exact selected pedestrian case: ' + args.case)
        return
    if not all((args.host, args.port, args.output, os.environ.get('SCENARIO_PEDESTRIAN_OPERATOR_MODULE'), os.environ.get('SCENARIO_PEDESTRIAN_OPERATOR_SHA256'))):
        raise ValueError('Reviewed original C109171 source operator and Native endpoint required')
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'capture', '--manifest', str(HERE / 'execution-manifest.json'), '--case', args.case, '--host', args.host, '--port', str(args.port), '--output', args.output], cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
