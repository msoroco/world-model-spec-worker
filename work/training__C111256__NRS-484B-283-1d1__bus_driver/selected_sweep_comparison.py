"""Compare the four exact selected sweep attempts after saved processing."""
import argparse
import json
from pathlib import Path

from sweep_comparison_audit import HERE, SUFFIXES, compare, require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior selected comparison output')
    attempts = {suffix: args.root / suffix / 'primary/selected-attempt'
                for suffix in SUFFIXES}
    processing = {suffix: args.root / suffix / 'primary/processed/v0001/processing.json'
                  for suffix in SUFFIXES}
    result = compare(attempts, processing, diagnostic=args.diagnostic,
                     manifest_path=args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'passed': result['passed'], 'diagnostic': args.diagnostic}))


if __name__ == '__main__':
    main()
