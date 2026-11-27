"""Exact materialized-case entrypoint for the prospective rider-arm Native run."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
_spec = importlib.util.spec_from_file_location(
    "_native_rider_runner", Path(__file__).resolve().parent / "native/runner.py")
_native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)
check, execute = _native.check, _native.execute


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    case = config.get("case_id") or config.get("selected_case_id")
    if args.check:
        print(json.dumps(check(case), sort_keys=True))
        return
    if args.output_dir is None:
        parser.error("--output-dir required for Native capture")
    print(json.dumps(execute(case, args.output_dir, host=args.host, port=args.port,
                             walker_blueprint=config.get("walker_blueprint",
                                                         "walker.pedestrian.0001"))))


if __name__ == "__main__":
    main()
