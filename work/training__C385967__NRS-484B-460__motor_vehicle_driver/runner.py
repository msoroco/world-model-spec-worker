"""Exact selected NRS 484B.460 angle parking Native entrypoint."""
import argparse
import json
from pathlib import Path

from capture import capture, check


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error("Original Native capture requires --output-dir, --host and --port")
        print(json.dumps(capture(config, args.output_dir, args.host, args.port), sort_keys=True))
