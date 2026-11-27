"""Exact C136495 Native entrypoint for worker materialization and local capture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "native"))
from runner import check, execute


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    case_id = config["selected_case_id"]
    condition = "clear" if case_id.endswith("__probe_a") else "intrusion"
    selection = ROOT / "candidate-selection.json"
    candidate = json.loads(selection.read_text())["candidate_id"] if selection.exists() else config["candidate_id"]
    if args.check:
        print(json.dumps(check(case_id, condition, config["duration_s"],
                               config["rate_hz"], candidate), sort_keys=True))
        return
    if not args.output_dir:
        parser.error("--output-dir is required for a Native capture")
    print(json.dumps(execute(Path(args.output_dir), case_id, condition,
                             args.host, args.port, candidate), sort_keys=True))


if __name__ == "__main__":
    main()
