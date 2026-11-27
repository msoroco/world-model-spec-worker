"""Exercise recorded-only processing for each of six exact variant fixtures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c386410-variant-saved'
MANIFEST = ROOT / 'execution-manifest.json'
VARIANTS = ('bus_stop', 'bus_stand', 'route_origin',
            'transient_stop', 'parking_other_street', 'tour_bus_other_street')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(args, log):
    result = subprocess.run([sys.executable, '-B', str(REPO / 'runtime.py'), *args],
                            cwd=REPO, capture_output=True, text=True,
                            env=dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH)))
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(' '.join(args[:2]) + ': ' + result.stderr[-1500:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for suffix in VARIANTS:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
        stage = SCRATCH / suffix
        recipe = ROOT / 'cases' / suffix / 'recipe.json'
        fixture = stage / 'fixture'
        attempt = stage / 'attempt'
        output = stage / 'output'
        if not fixture.is_dir():
            call(['fixture', '--recipe', str(recipe), '--output', str(fixture)], stage / 'fixture.log')
        if not attempt.is_dir():
            call(['materialize', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                  '--output', str(attempt)], stage / 'materialize.log')
            for source in fixture.iterdir():
                target = attempt / source.name
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
        if not (output / 'v0001/processing.json').is_file():
            call(['process-saved', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                  '--attempt', str(attempt), '--output', str(output),
                  '--library', str(REPO / 'runtime/library'),
                  '--validator', str(REPO / '.runtime-work/c386410-decoder/.lake/build/bin/adapterCheck')],
                 stage / 'saved-command.log')
        receipt = json.loads((output / 'v0001/processing.json').read_text())
        if not receipt.get('passed') or receipt.get('missing_evidence'):
            raise ValueError('Saved processing incomplete: ' + suffix)
        proof = ROOT / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage / 'saved-command.log', proof / 'saved.log')
        shutil.copyfile(output / 'v0001/processing.json', proof / 'processing.json')
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' + ROOT.name + '/execution-manifest.json --case ' + entry['case_id'] + ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json',
            'test_exit_code': 0, 'test_log': 'proofs/' + suffix + '/saved.log',
            'test_log_sha256': sha(proof / 'saved.log'),
            'processing_receipt': 'proofs/' + suffix + '/processing.json',
            'processing_receipt_sha256': sha(proof / 'processing.json')}
        print('saved-only passed', suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
