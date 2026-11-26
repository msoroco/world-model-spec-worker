"""Exercise selected recorded-only processing with current source-shaped evidence."""
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
    result = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise ValueError(result.stdout[-500:] + result.stderr[-2500:])
    return result


def run(suffix, validator):
    if suffix not in ('a', 'b', 'c'):
        raise ValueError('Unknown selected case')
    case = FOLDER.name + '__probe_' + suffix
    manifest = FOLDER / 'execution-manifest.json'
    recipe = HERE / f'selected-{suffix}-fixture-recipe.json'
    scratch = ROOT / '.runtime-work'
    with tempfile.TemporaryDirectory(dir=scratch, prefix=f'c42387-saved-{suffix}-') as temp:
        temp = Path(temp)
        source, attempt, output = temp/'source', temp/'attempt', temp/'processed'
        call('fixture','--recipe',recipe,'--output',source)
        call('offline','--manifest',manifest,'--case',case,'--output',attempt)
        for item in source.iterdir():
            target = attempt/item.name
            if target.exists():
                raise ValueError('Source shadows selected construction: '+item.name)
            if item.is_dir():
                shutil.copytree(item,target)
            else:
                shutil.copyfile(item,target)
        (attempt/'candidate-selection.json').unlink()
        positive = call('process-saved','--manifest',manifest,'--case',case,
            '--attempt',attempt,'--output',output,'--library',ROOT/'runtime/library',
            '--validator',validator)
        receipt = json.loads((output/'v0001/processing.json').read_text())
        if not (receipt['passed'] is True and receipt['recorded_only'] is True and
                receipt['missing_evidence'] is False and
                receipt['timestamp_joins']['frames'] == 600 and
                receipt['final_video_checks']['frames'] == 600):
            raise ValueError('Positive selected saved-processing result incomplete')
        positive_copy=temp/'positive-receipt.json'
        shutil.copyfile(output/'v0001/processing.json',positive_copy)
        os.replace(positive_copy,HERE/f'selected-{suffix}-saved-receipt.json')
        negative_attempt = temp/'negative-attempt'
        shutil.copytree(attempt,negative_attempt)
        (negative_attempt/'control_context.json').unlink()
        negative_output = temp/'negative-processed'
        negative = call('process-saved','--manifest',manifest,'--case',case,
            '--attempt',negative_attempt,'--output',negative_output,
            '--library',ROOT/'runtime/library','--validator',validator)
        feedback = json.loads((negative_output/'v0001/feedback.json').read_text())
        negative_receipt = json.loads((negative_output/'v0001/processing.json').read_text())
        if not (feedback['recorded_only'] is True and
                feedback['native_replay_requested'] is False and
                'Missing required source: control_context.json' in feedback['error'] and
                negative_receipt['missing_evidence'] is True):
            raise ValueError('Missing-source saved-processing feedback incomplete')
        negative_copy=temp/'negative-feedback.json'
        shutil.copyfile(negative_output/'v0001/feedback.json',negative_copy)
        os.replace(negative_copy,HERE/f'selected-{suffix}-saved-negative-feedback.json')
        return {'case_id':case,'recorded_only':True,'positive_exit_code':positive.returncode,
            'negative_exit_code':negative.returncode,'positive_processing_sha256':
                sha(HERE/f'selected-{suffix}-saved-receipt.json'),
            'negative_feedback_sha256':
                sha(HERE/f'selected-{suffix}-saved-negative-feedback.json'),
            'diagnostic_fixture':True,'original_native_executed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', choices=('a','b','c'), required=True)
    parser.add_argument('--validator', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.condition,args.validator.resolve()),sort_keys=True))
