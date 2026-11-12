"""Run source-bound positive and negative compatibility for every fallback."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in entry['candidates']:
            ident = candidate['id']
            output = REPO / '.runtime-work' / f'c158190-{suffix}-{ident}-compat-v2'
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST),
                       '--case', entry['case_id'], '--candidate', ident,
                       '--output', str(output), '--library', str(REPO / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            if not (output / 'compatibility.json').is_file():
                env = dict(os.environ)
                env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c158190-output-root-20261111')
                result = subprocess.run(command, cwd=REPO, capture_output=True,
                                        text=True, env=env)
                if result.returncode:
                    failure = ROOT / candidate['construction']
                    failure = failure.parent / f'{ident}-compatibility-run.log'
                    failure.write_text(result.stdout[-30000:] + result.stderr[-30000:])
                    raise ValueError(f'{suffix} {ident}: compatibility exited {result.returncode}; see {failure}')
            source = json.loads((output / 'compatibility.json').read_text())
            if not source.get('passed') or source.get('candidate_id') != ident:
                raise ValueError(f'{suffix} {ident}: compatibility receipt failed')
            folder = (ROOT / candidate['construction']).parent
            destinations = {}
            for source_name, dest_name in (
                    ('compatibility.json', f'{ident}-compatibility.json'),
                    ('compatibility-analysis.log', f'{ident}-compatibility-analysis.log'),
                    ('negative-analysis.log', f'{ident}-negative-analysis.log')):
                path = folder / dest_name
                shutil.copyfile(output / source_name, path)
                destinations[source_name] = path
            candidate['compatibility'] = {
                'receipt': str(destinations['compatibility.json'].relative_to(ROOT)),
                'sha256': sha(destinations['compatibility.json']),
                'log': str(destinations['compatibility-analysis.log'].relative_to(ROOT)),
                'negative_log': str(destinations['negative-analysis.log'].relative_to(ROOT)),
                'replay_command': ' '.join(Path(x).relative_to(REPO).as_posix()
                                           if x.startswith(str(REPO) + '/') else x for x in command),
            }
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(json.dumps({'case': suffix, 'candidate': ident,
                              'passed': True, 'receipt': candidate['compatibility']['receipt']}),
                  flush=True)


if __name__ == '__main__':
    main()
