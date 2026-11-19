"""Positive and negative source-bound C109705(2b) CPU audit proofs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from independent_audits import REQUIRED, audit_comparison, audit_delivery


def reject(fn, fragment):
    try:
        fn()
    except ValueError as error:
        if fragment not in str(error):
            raise
        print('negative:', error)
    else:
        raise AssertionError('Expected rejection: ' + fragment)


def clone(attempt, target):
    for name in (*REQUIRED, 'result.json'):
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.link(attempt / name, dest)


def change_json(target, name, update):
    path = target / name
    value = json.loads(path.read_text())
    update(value)
    path.unlink()
    path.write_text(json.dumps(value, sort_keys=True) + '\n')
    result = target / 'result.json'
    data = json.loads(result.read_text())
    data['source_evidence_hashes'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result.unlink()
    result.write_text(json.dumps(data, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser()
    for name in ('marked_near', 'marked_far', 'imaginary_near', 'imaginary_far'):
        parser.add_argument('--' + name.replace('_', '-'), required=True, type=Path)
    args = parser.parse_args()
    for kind, near, far in (('marked', args.marked_near, args.marked_far),
                            ('imaginary', args.imaginary_near, args.imaginary_far)):
        print(json.dumps(audit_comparison(near, far, kind, decode=True), sort_keys=True))
        reject(lambda: audit_comparison(near, far, 'wrong'), 'Wrong comparison centerline kind')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            clone(near, target)
            (target / 'turn_history.jsonl').unlink()
            reject(lambda: audit_delivery(target), 'Missing original evidence')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            clone(far, target)
            change_json(target, 'road_context.json', lambda x: x.__setitem__('outgoing_road_id', 9))
            reject(lambda: audit_comparison(near, target, kind), 'Original context/packet mismatch')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            clone(far, target)
            change_json(target, 'road_context.json', lambda x: x.__setitem__('opposing_lane_source', 'different-reviewed-source'))
            reject(lambda: audit_comparison(near, target, kind), 'Fixed comparison condition differs')
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            target = Path(tmp)
            clone(near, target)
            result = target / 'result.json'
            data = json.loads(result.read_text())
            data['measured_values']['body_centroid_distance_to_centerline_m'] += 0.5
            result.unlink()
            result.write_text(json.dumps(data) + '\n')
            reject(lambda: audit_delivery(target), 'Reported measurement differs')
    print('Independent synthetic diagnostic delivery and comparison audits passed')


if __name__ == '__main__':
    main()
