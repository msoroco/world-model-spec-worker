"""Select one exact C125714 construction from the source-hashed delivery manifest."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import select
from worker_exchange.runtime_cli import materialize


def dispatch(case, candidate, output, host, port, check_only):
    manifest = HERE / 'execution-manifest.json'
    entry, selected, construction = select(manifest, case, candidate)
    if entry.get('kind') != 'delivery':
        raise ValueError('Exact case is not a delivery construction')
    config = json.loads((HERE / 'config.json').read_text())
    if case not in config['supported_case_ids']:
        raise ValueError('Case not supported by canonical configuration')
    if check_only:
        with TemporaryDirectory(prefix='c125714-check-', dir=ROOT / '.runtime-work') as temp:
            target = Path(temp) / 'attempt'
            materialize(manifest, case, target, candidate)
            command = [sys.executable, str(target / construction['entrypoint']),
                       '--check', '--config', str(target / 'config.json')]
            subprocess.run(command, cwd=target, check=True)
        return {'case_id': case, 'candidate': selected['id'], 'offline_checked': True}
    if not output:
        raise ValueError('Fresh Native output directory required')
    target = Path(output).resolve()
    materialize(manifest, case, target, candidate)
    command = [sys.executable, str(target / construction['entrypoint']),
               '--run', '--config', str(target / 'config.json'), '--output', str(target),
               '--host', host, '--port', str(port)]
    subprocess.run(command, cwd=target, check=True)
    return {'case_id': case, 'candidate': selected['id'], 'native_output': str(target)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(dispatch(args.case, args.candidate, args.output,
                              args.host, args.port, args.check), indent=2))


if __name__ == '__main__':
    main()
