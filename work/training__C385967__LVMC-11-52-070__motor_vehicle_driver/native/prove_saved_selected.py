"""Exercise exact selected recorded-only processing and missing-source feedback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(*args):
    p = subprocess.run([sys.executable, '-B', str(ROOT / 'runtime.py'), *map(str, args)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise ValueError(p.stdout[-500:] + p.stderr[-3000:])
    return p


def run(suffix, validator):
    case = FOLDER.name + '__probe_' + suffix
    scratch = ROOT / '.runtime-work'
    manifest = FOLDER / 'execution-manifest.json'
    with tempfile.TemporaryDirectory(dir=scratch, prefix=f'c385967-saved-{suffix}-') as name:
        temp = Path(name)
        source, attempt, output = temp/'source', temp/'attempt', temp/'processed'
        call('fixture', '--recipe', HERE/f'selected-{suffix}-fixture-recipe.json',
             '--output', source)
        call('offline', '--manifest', manifest, '--case', case, '--output', attempt)
        for item in source.iterdir():
            target = attempt/item.name
            if target.exists():
                raise ValueError('Fixture shadows selected construction: ' + item.name)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copyfile(item, target)
        (attempt/'candidate-selection.json').unlink()
        call('process-saved', '--manifest', manifest, '--case', case,
             '--attempt', attempt, '--output', output,
             '--library', ROOT/'runtime/library', '--validator', validator)
        receipt = json.loads((output/'v0001/processing.json').read_text())
        if not (receipt['passed'] is True and receipt['recorded_only'] is True and
                receipt['missing_evidence'] is False and
                receipt['timestamp_joins']['frames'] == 600 and
                receipt['final_video_checks']['frames'] == 600):
            raise ValueError('Recorded-only positive incomplete')
        shutil.copyfile(output/'v0001/processing.json', HERE/f'selected-{suffix}-saved-processing.json')
        negative_attempt = temp/'negative-attempt'
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt/'permission_authority.json').unlink()
        negative_output = temp/'negative-processed'
        call('process-saved', '--manifest', manifest, '--case', case,
             '--attempt', negative_attempt, '--output', negative_output,
             '--library', ROOT/'runtime/library', '--validator', validator)
        feedback = json.loads((negative_output/'v0001/feedback.json').read_text())
        negative = json.loads((negative_output/'v0001/processing.json').read_text())
        if not (feedback['recorded_only'] is True and
                feedback['native_replay_requested'] is False and
                'Missing required source: permission_authority.json' in feedback['error'] and
                negative['missing_evidence'] is True):
            raise ValueError('Recorded-only missing-authority feedback incomplete')
        shutil.copyfile(negative_output/'v0001/feedback.json',
                        HERE/f'selected-{suffix}-saved-negative-feedback.json')
        return {'case_id':case, 'recorded_only':True, 'positive_exit_code':0,
                'negative_exit_code':0,
                'positive_processing_sha256':sha(HERE/f'selected-{suffix}-saved-processing.json'),
                'negative_feedback_sha256':sha(HERE/f'selected-{suffix}-saved-negative-feedback.json'),
                'diagnostic_fixture':True, 'original_native_executed':False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--condition', choices=('a', 'b'), required=True)
    p.add_argument('--validator', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.condition, a.validator.resolve()), sort_keys=True))
