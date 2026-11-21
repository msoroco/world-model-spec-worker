"""Dispatch one selected C183370 case through the pinned runtime.

This package entrypoint checks exact selections on CPU. Native capture is only
started by an explicit ``--capture`` call with a supplied CARLA interpreter.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
MANIFEST = HERE / 'execution-manifest.json'


def selection(case_id, candidate_id):
    sys.path.insert(0, str(ROOT / 'runtime' / 'pipeline'))
    from scenario_pipeline.worker_exchange.candidate_constructions import select
    from scenario_pipeline.worker_exchange.common import sha

    configuration = json.loads((HERE / 'config.json').read_text())
    if configuration['actor'] != 'motor_vehicle_driver' or configuration['law_id'] != 'LVMC-11-22-100':
        raise ValueError('Package identity changed')
    if case_id not in configuration['supported_case_ids']:
        raise ValueError('Case is outside this package')
    entry, selected, construction = select(MANIFEST, case_id, candidate_id)
    if construction['entrypoint'] != 'runner.py':
        raise ValueError('Selected bundle has no canonical runner')
    for file in construction['files']:
        if file.get('source') and sha(ROOT / file['source']) != sha_text(file['content']):
            raise ValueError('Selected source changed: ' + file['path'])
    return {'case_id': entry['case_id'], 'candidate_id': selected['id'],
            'construction_sha256': selected['construction_sha256'],
            'original_native_observed': False}


def sha_text(content):
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary',
                        choices=('primary', 'fallback1', 'fallback2', 'fallback3'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--python')
    parser.add_argument('--host')
    parser.add_argument('--port')
    args = parser.parse_args()
    selected = selection(args.case, args.candidate)
    if args.check:
        print(json.dumps(selected, sort_keys=True))
        return
    if not args.output:
        parser.error('--output is required to materialize an exact case')
    command = [sys.executable, str(ROOT / 'runtime.py'),
               'capture' if args.capture else 'materialize',
               '--manifest', str(MANIFEST), '--case', args.case,
               '--candidate', args.candidate, '--output', args.output]
    if args.capture:
        if not all((args.python, args.host, args.port)):
            parser.error('Native capture requires --python, --host and --port')
        command += ['--python', args.python, '--host', args.host, '--port', args.port]
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
