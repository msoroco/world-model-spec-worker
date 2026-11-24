"""Canonical exact-case index for C10301 speed-boundary delivery."""
import argparse
import json
from pathlib import Path


def select(case_id):
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'execution-manifest.json').read_text())
    matches = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Select one exact speed-boundary case')
    return root / matches[0]['construction']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(select(args.case))


if __name__ == '__main__':
    main()
