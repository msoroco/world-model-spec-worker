"""Dispatch an exact selected school-zone case to its Native runner.

The reviewed survey and CARLA connection are supplied only at local execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def exact_runner(case_id):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact school-zone case')
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix == 'probe_03':
        path = HERE / 'native/selected_primary/runner.py'
    elif suffix in {'probe_01', 'probe_02', 'probe_04', 'probe_05',
                    'probe_06', 'probe_07', 'probe_08'}:
        path = HERE / 'native/cases' / suffix / 'runner.py'
    else:
        raise ValueError('Unknown school-zone case')
    if not path.is_file():
        raise ValueError('Exact Native runner missing')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    native = exact_runner(args.case)
    command = [sys.executable, str(native)]
    if args.check:
        command.append('--check')
    else:
        if args.survey is None or args.output_dir is None:
            parser.error('Supply reviewed --survey and --output-dir')
        command.extend(['--survey', str(args.survey), '--output-dir',
                        str(args.output_dir), '--host', args.host, '--port',
                        str(args.port)])
    return subprocess.call(command)


if __name__ == '__main__':
    raise SystemExit(main())
