"""Exact Native road-to-driveway entrypoint."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from runner import check, capture
if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if not args.output_dir:
            raise SystemExit('Exact Native attempt directory required')
        print(json.dumps(capture(args.output_dir, 'stop_before_sidewalk', args.host, args.port)))
