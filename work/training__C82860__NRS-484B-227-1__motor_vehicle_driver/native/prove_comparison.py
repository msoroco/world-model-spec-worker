"""Exercise the saved comparison on exact diagnostic acquisition copies."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from comparison_audit import audit


def prove(opening, barrier, negative):
    opening, barrier = Path(opening), Path(barrier)
    if not negative:
        result = audit(opening, barrier)
        if result["controlled_difference"] != "median_crossing_location" or not result["fixed_context_checked"]:
            raise AssertionError("Comparison did not establish fixed context")
        print(json.dumps(result, indent=2))
        return
    with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
        copy = Path(temp) / "barrier"
        shutil.copytree(barrier, copy)
        cfg = copy / "config.json"
        value = json.loads(cfg.read_text())
        value["duration_s"] = 29
        cfg.write_text(json.dumps(value) + "\n")
        audit(opening, copy)
        raise AssertionError("Changed fixed duration passed comparison audit")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--opening", required=True)
    parser.add_argument("--barrier", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    prove(args.opening, args.barrier, args.negative)
