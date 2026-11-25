"""Reject a changed fixed camera contract in a saved comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    args = parser.parse_args()
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = next(c["case_ids"] for c in plan["comparisons"]
                 if c["comparison_id"] == args.comparison)
    with tempfile.TemporaryDirectory(prefix="comparison-negative-", dir=REPO / ".runtime-work/c378304") as temp:
        roots = []
        for case_id in cases:
            tag = case_id.rsplit("__", 1)[-1]
            source = REPO / ".runtime-work/c378304" / ("compatibility-" + tag + "-primary-evidence-v2")
            target = Path(temp) / tag
            target.mkdir()
            for name in ("original-turn-signal.json", "original-site.json", "acquisition.json",
                         "config.json", "fixture-provenance.json"):
                shutil.copy2(source / name, target / name)
            roots.append(target)
        config = json.loads((roots[-1] / "config.json").read_text())
        config["cameras"][0]["width"] += 1
        (roots[-1] / "config.json").write_text(json.dumps(config) + "\n")
        try:
            audit(args.comparison, roots)
        except ValueError as error:
            if "fixed comparison construction differs" not in str(error):
                raise
            print("fixed comparison construction differs; changed camera contract rejected")
            return
        raise AssertionError("changed fixed camera contract accepted")


if __name__ == "__main__":
    main()
