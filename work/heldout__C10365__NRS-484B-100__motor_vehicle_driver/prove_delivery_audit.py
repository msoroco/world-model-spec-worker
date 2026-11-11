"""Run an independent officer delivery audit, optionally deleting one copied source."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from delivery_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.negative:
        with tempfile.TemporaryDirectory(prefix='officer-delivery-negative-') as temporary:
            attempt = Path(temporary) / 'attempt'
            shutil.copytree(args.attempt, attempt)
            (attempt / 'officer_direction.json').unlink()
            print(json.dumps(audit(args.case, attempt), indent=2))
    else:
        print(json.dumps(audit(args.case, Path(args.attempt)), indent=2))


if __name__ == '__main__':
    main()
