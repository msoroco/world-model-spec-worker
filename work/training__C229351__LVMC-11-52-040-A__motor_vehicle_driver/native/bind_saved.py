"""Exercise saved-only processing on immutable primary diagnostic acquisitions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'
DECODER = ROOT / '.runtime-work/c229351-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    directory = FOLDER / 'saved'
    directory.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work'))
    for index, entry in enumerate(manifest['cases']):
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        source = ROOT / f'.runtime-work/c229351-compat-v6-{index}-primary'
        attempt = ROOT / f'.runtime-work/c229351-saved-source-v3-{index}-primary'
        output = ROOT / f'.runtime-work/c229351-saved-v3-{index}-primary'
        shutil.copytree(source, attempt, copy_function=os.link)
        # Compatibility materialized before all proof bindings; a local actual
        # capture receives a selection receipt from its final frozen manifest.
        (attempt / 'candidate-selection.json').unlink()
        command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST), '--case', case,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
        log = directory / f'{suffix}-processing.log'
        with log.open('w') as stream:
            status = subprocess.run(command, cwd=ROOT, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT)
        if status.returncode:
            raise RuntimeError(f'Saved-only processing failed: {log}')
        processing = output / 'v0001/processing.json'
        receipt = json.loads(processing.read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
                or receipt.get('originals_preserved') is not True or
                receipt.get('candidate_id') != 'primary'):
            raise ValueError('Saved-only source preservation or selection missing')
        receipt_path = directory / f'{suffix}-processing.json'
        shutil.copy2(processing, receipt_path)
        portable = f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER'
        entry['post_capture'] = {'command': portable, 'feedback_command': portable,
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': str(log.relative_to(FOLDER)), 'test_log_sha256': sha(log),
            'processing_receipt': str(receipt_path.relative_to(FOLDER)),
            'processing_receipt_sha256': sha(receipt_path),
            'test_scope': 'synthetic saved diagnostic; original Native pending'}
        MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
        print(index, suffix, 'saved-only processing passed', flush=True)


if __name__ == '__main__':
    main()
