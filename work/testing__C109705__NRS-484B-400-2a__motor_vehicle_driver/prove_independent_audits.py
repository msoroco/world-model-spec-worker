"""Exercise independent C109705 audits on retained CPU source attempts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from independent_audits import REQUIRED, audit_comparison, audit_delivery


def expect_error(fn, fragment):
    try:
        fn()
    except ValueError as error:
        if fragment not in str(error):
            raise
        print('negative:', error)
    else:
        raise AssertionError('Expected rejection: ' + fragment)


def main():
    parser = argparse.ArgumentParser()
    for name in ('marked_near', 'marked_far', 'imaginary_near', 'imaginary_far'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    args = parser.parse_args()
    pairs = [('marked', Path(args.marked_near), Path(args.marked_far)),
             ('imaginary', Path(args.imaginary_near), Path(args.imaginary_far))]
    for kind, near, far in pairs:
        print(json.dumps(audit_comparison(near, far, kind), sort_keys=True))
        expect_error(lambda: audit_comparison(near, far, 'wrong'), 'Wrong comparison centerline kind')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            for name in REQUIRED:
                os.link(near / name, target / name)
            (target / 'approach_history.jsonl').unlink()
            expect_error(lambda: audit_delivery(target), 'Missing original evidence')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            for name in REQUIRED:
                os.link(far / name, target / name)
            context_path = target / 'road_context.json'
            context = json.loads(context_path.read_text())
            context['outgoing_road_id'] = 9
            context_path.unlink()
            context_path.write_text(json.dumps(context))
            result_path = target / 'result.json'
            result = json.loads(result_path.read_text())
            result['source_evidence_hashes']['road_context.json'] = hashlib.sha256(context_path.read_bytes()).hexdigest()
            result_path.unlink()
            result_path.write_text(json.dumps(result))
            expect_error(lambda: audit_comparison(near, target, kind), 'Fixed comparison condition differs')
    print('Independent diagnostic delivery and comparison audit proofs passed')


if __name__ == '__main__':
    main()
