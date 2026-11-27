"""Materialize one exact source-bound taxi construction for CPU offline proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C378245__LVMC-11-60-040__taxi_driver"
SUFFIX = "outside_stand_park"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    case = next(c for c in plan["cases"] if c["case_id"] == ASSIGNMENT + "__" + SUFFIX)
    names = ["runner.py", "native_taxi_operator.py", "encode_taxi_views.py", "taxi_stand_measurement.py", "analysis.py",
             "case-plan.json", "config.json", "tests/test_runner.py",
             "tests/test_native_taxi_operator.py", "tests/test_taxi_stand_measurement.py"]
    files = [{"path": name, "content": (ROOT / name).read_text(),
              "source": "work/" + ASSIGNMENT + "/" + name} for name in names]
    construction = {
        "case_id": case["case_id"], "cell_id": "C378245", "law_id": "LVMC-11-60-040",
        "actor": "taxi_driver", "entrypoint": "runner.py",
        "recording_description": case["recording_description"],
        "measurement_plan": {"stand": "Source-hashed taxi body footprint inside/outside officially reviewed designated stand",
                             "passenger": "Independent actual loading/unloading and expeditiousness review, not requested activity",
                             "other_regulations": "Independent source review of applicable stop/parking rules"},
        "static_checks": ["exact C378245 case/config selection",
                          "source SHA-256 before Native import",
                          "900 synchronized original frames and four camera views"],
        "mechanisms": ["reviewed original Native map and stand site",
                       "four synchronized RGB cameras",
                       "saved original taxi body and velocity samples"],
        "termination_rules": ["stop at 900 Native ticks", "fail on source or camera mismatch"],
        "files": files,
    }
    path = ROOT / "cases" / SUFFIX / "construction.json"
    write(path, construction)
    manifest = {"format": "worker-execution-manifest-draft", "assignment_id": ASSIGNMENT,
                "cases": [{"case_id": case["case_id"], "kind": "delivery",
                           "construction": "cases/" + SUFFIX + "/construction.json",
                           "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
    write(ROOT / "execution-manifest.draft.json", manifest)


if __name__ == "__main__":
    build()
    print("outside-stand parking construction bound")
