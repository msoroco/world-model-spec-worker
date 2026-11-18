"""Reject a missing original backing stream in a fresh source-only saved copy."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

from delivery_audit import audit


def main(case, attempt):
    workspace = Path(__file__).resolve().parents[2] / '.runtime-work'
    with tempfile.TemporaryDirectory(prefix='c110779-negative-', dir=workspace) as directory:
        staged = Path(directory) / 'analysis'
        shutil.copytree(attempt, staged, copy_function=os.link)
        (staged / 'backing_motion.jsonl').unlink()
        try:
            audit(case, staged)
        except ValueError as error:
            if 'Missing required source: backing_motion.jsonl' not in str(error):
                raise
            print(str(error))
            raise SystemExit(1)
        raise ValueError('Missing original backing source was accepted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    main(args.case, args.attempt)
