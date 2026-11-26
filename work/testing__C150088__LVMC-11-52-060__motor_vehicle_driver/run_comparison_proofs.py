"""Test fixed-condition and deliberate-difference comparison audit branches."""

import hashlib
import json
import shutil
from pathlib import Path

from comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    scratch = REPO / ".runtime-work/c150088-nov26/comparison-proofs-v1"
    scratch.mkdir(parents=True, exist_ok=True)
    positive = scratch / "positive"
    positive.mkdir(exist_ok=True)
    for suffix in ("vehicle_below", "vehicle_equal", "vehicle_above", "load_above", "trailer_above"):
        log = ROOT / ("audit-" + suffix + "-positive.log")
        report = json.loads(log.read_text(encoding="utf-8"))
        (positive / (suffix + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    for item in plan["comparisons"]:
        name = item["comparison_id"]
        result = audit(name, positive, synthetic_fixture=True)
        target = ROOT / ("comparison-" + name + "-positive.json")
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        negative = scratch / (name + "-negative")
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(positive, negative)
        member = item["case_ids"][-1].rsplit("__", 1)[-1]
        path = negative / (member + ".json")
        bad = json.loads(path.read_text(encoding="utf-8"))
        bad["road_sha256"] = "0" * 64
        path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
        try:
            audit(name, negative, synthetic_fixture=True)
        except ValueError as error:
            if "changed fixed curb" not in str(error):
                raise
            failure = str(error)
        else:
            raise ValueError("changed fixed condition was accepted: " + name)
        log = ROOT / ("comparison-" + name + "-negative.log")
        log.write_text(failure + "\n", encoding="utf-8")
        print(name, "positive and negative passed", sha(target), flush=True)


if __name__ == "__main__":
    main()
