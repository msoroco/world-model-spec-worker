"""Run the independent audit after removing one original source."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from delivery_audit import audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    original = Path(args.attempt).resolve()
    with TemporaryDirectory(prefix='backing-audit-negative-') as temp:
        attempt = Path(temp)
        for path in original.iterdir():
            if path.name != 'backing_motion.jsonl':
                (attempt / path.name).symlink_to(path)
        audit(args.case, attempt)
    raise AssertionError('Audit accepted missing original backing motion')
