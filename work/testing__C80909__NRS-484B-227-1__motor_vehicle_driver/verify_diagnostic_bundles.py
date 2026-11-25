"""Materialize four exact partial constructions and run CPU-only checks."""

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
DESTINATION = REPO / '.runtime-work/c80909-diagnostic-materialization'
SUFFIXES = ('left_through_opening', 'left_across_blocked_divider',
            'left_at_established_crossover', 'left_right_roadway_continuation')


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    logs = []
    for suffix in SUFFIXES:
        manifest_path = ROOT / 'construction.json' if suffix == SUFFIXES[0] else ROOT / 'cases' / suffix / 'construction.json'
        manifest = json.loads(manifest_path.read_text())
        destination = DESTINATION / suffix
        destination.mkdir(exist_ok=True)
        for entry in manifest['files']:
            source = REPO / entry['source']
            if source.read_text() != entry['content']:
                raise ValueError('Stale exact construction source: ' + str(source))
            target = (destination / entry['path']).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Unsafe materialized path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry['content'])
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for command in ([str(PYTHON), 'runner.py', '--check'],
                        [str(PYTHON), '-m', 'unittest', 'discover', '-s', 'tests', '-v']):
            result = subprocess.run(command, cwd=destination, env=environment,
                                    capture_output=True, text=True)
            logs.append(suffix + ' ' + ('check' if '--check' in command else 'tests') +
                        ' exit=' + str(result.returncode) + '\n' + result.stdout + result.stderr)
            if result.returncode:
                (ROOT / 'diagnostic-materialization.log').write_text('\n'.join(logs))
                raise SystemExit(1)
    (ROOT / 'diagnostic-materialization.log').write_text('\n'.join(logs))
    print('Four exact diagnostic bundles passed runner --check and focused CPU tests')


if __name__ == '__main__':
    main()
