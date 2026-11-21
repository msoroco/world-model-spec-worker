"""Audit one selected comparison against its current exact CPU source labels."""
import argparse
import hashlib
import json
from pathlib import Path

import audit_selected_same_cell_comparisons as comparison

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    if path.exists():
        raise ValueError('Retain previous comparison audit: ' + str(path))
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=comparison.PAIRS, required=True)
    parser.add_argument('--left-label', required=True)
    parser.add_argument('--right-label', required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    left, right, _ = comparison.PAIRS[args.comparison]
    comparison.SOURCE_LABELS[left] = args.left_label
    comparison.SOURCE_LABELS[right] = args.right_label
    positive = comparison.audit(args.comparison)
    positive_path = HERE / (args.tag + '-comparison.json')
    write_new(positive_path, positive)
    try:
        comparison.audit(args.comparison, swapped=True)
    except ValueError as error:
        negative = {'passed': True, 'rejection': str(error)}
    else:
        raise AssertionError('Swapped sources were accepted')
    negative_path = HERE / (args.tag + '-comparison-swapped-negative.json')
    write_new(negative_path, negative)
    print(json.dumps({'comparison': args.comparison,
                      'positive_sha256': sha(positive_path),
                      'swapped_negative_sha256': sha(negative_path),
                      'diagnostic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
