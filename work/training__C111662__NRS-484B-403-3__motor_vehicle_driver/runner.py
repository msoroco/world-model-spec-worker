"""Dispatch one exact U-turn case to its selected runtime construction."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('offline', 'capture'), required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'),
                        default='primary')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--host')
    parser.add_argument('--port')
    args = parser.parse_args()
    config = json.loads((HERE / 'config.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if args.case not in config['supported_case_ids']:
        raise ValueError('Case is outside exact selected assignment')
    entry = next(e for e in manifest['cases'] if e['case_id'] == args.case)
    if args.candidate != 'primary' and args.candidate not in {e['id'] for e in entry['candidates']}:
        raise ValueError('Unknown exact fallback')
    command = [args.python, str(REPO / 'runtime.py'), args.mode,
               '--manifest', str(HERE / 'execution-manifest.json'), '--case', args.case,
               '--candidate', args.candidate, '--output', str(args.output.resolve()),
               '--python', args.python]
    if args.mode == 'capture':
        if not args.host or not args.port:
            raise ValueError('Native capture needs an explicit host and port')
        command += ['--host', args.host, '--port', args.port]
    subprocess.run(command, cwd=REPO, check=True)


if __name__ == '__main__':
    main()
