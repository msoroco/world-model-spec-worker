"""Exercise recorded-only rail-stop processing on fresh source-shaped attempts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-native-manifest.json'
DECODER = ROOT / '.runtime-work/nrs-decoder/.lake/build/bin/adapterCheck'
BASE = ROOT / '.runtime-work/c25835-owner/saved'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(tokens, log=None):
    result = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
             'SCENARIO_PIPELINE_OUTPUT_ROOT': str(ROOT / '.runtime-work/c25835-owner'),
             'TMPDIR': str(ROOT / '.runtime-work')})
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Failed: ' + ' '.join(tokens) + '\n' + result.stderr[-2500:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        fixture = BASE / ('fixture-' + suffix + '-v1')
        attempt = BASE / ('attempt-' + suffix + '-v1')
        output = BASE / ('output-' + suffix + '-v1')
        run([sys.executable, str(ROOT / 'runtime.py'), 'fixture', '--recipe',
             str(HERE / ('diagnostic-' + suffix + '-recipe.json')),
             '--output', str(fixture)])
        run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
             '--manifest', str(MANIFEST), '--case', case,
             '--output', str(attempt)])
        for path in fixture.iterdir():
            target = attempt / path.name
            if target.exists():
                continue
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        log = HERE / 'proofs' / suffix / 'saved.log'
        run([sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
             '--manifest', str(MANIFEST), '--case', case,
             '--attempt', str(attempt), '--output', str(output),
             '--library', str(ROOT / 'runtime/library'),
             '--validator', str(DECODER)], log)
        processing = json.loads((output / 'v0001/processing.json').read_text())
        if processing.get('passed') is not True or processing.get('recorded_only') is not True:
            raise ValueError('Recorded-only proof did not pass: ' + case)
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + HERE.name +
                       '/execution-manifest.json --case ' + case +
                       ' --attempt ATTEMPT --output OUTPUT --library runtime/library --validator VALIDATOR',
            'feedback_command': 'cat OUTPUT/feedback.json',
            'test_log': str(log.relative_to(HERE)),
            'test_log_sha256': sha(log), 'test_exit_code': 0}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(suffix, 'recorded-only saved processing passed', flush=True)


if __name__ == '__main__':
    main()
