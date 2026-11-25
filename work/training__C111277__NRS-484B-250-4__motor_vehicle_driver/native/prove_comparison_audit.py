"""Exercise independent comparison audit and its source rejection branches."""
import json
from pathlib import Path
import shutil
import tempfile

from comparison_audit import audit
from generate_fixture import make

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / '.runtime-work'


def rejected(halt, roll, expected):
    try:
        audit(halt, roll)
    except ValueError as error:
        if expected in str(error):
            return str(error)
        raise
    raise AssertionError('expected rejection: ' + expected)


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='c111277-comparison-') as directory:
        root = Path(directory)
        halt, roll = root / 'halt', root / 'roll'
        make(halt, 'halt')
        make(roll, 'roll')
        positive = audit(halt, roll)
        missing = root / 'missing'
        shutil.copytree(halt, missing)
        (missing / 'signal.json').unlink()
        missing_error = rejected(missing, roll, 'missing signal.json')
        changed = root / 'changed'
        shutil.copytree(halt, changed)
        with (changed / 'native-rows.jsonl').open('a') as stream:
            stream.write('\n')
        changed_error = rejected(changed, roll, 'source hash mismatch: native-rows.jsonl')
        no_contrast_error = rejected(roll, roll, 'comparison condition identities changed')
    report = {'format': 'nrs-484b-250-4-comparison-audit-proof-v1',
              'passed': True, 'positive': positive,
              'missing_source_rejection': missing_error,
              'changed_source_rejection': changed_error,
              'no_contrast_rejection': no_contrast_error,
              'original_native_observed': False}
    target = HERE / 'comparison-audit-proof.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_checks': 3}))


if __name__ == '__main__':
    main()
