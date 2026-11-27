"""Build the five remaining exact taxi constructions from shared sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDENTITY = "testing__C378245__LVMC-11-60-040__taxi_driver"
FIRST = "outside_stand_park"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 1 or manifest["cases"][0]["case_id"] != IDENTITY + "__" + FIRST:
        raise ValueError("first proven taxi case must remain pinned")
    shared = ["runner.py", "native_taxi_operator.py", "encode_taxi_views.py", "taxi_stand_measurement.py", "analysis.py",
              "case-plan.json", "tests/test_exact_case_config.py",
              "tests/test_native_taxi_operator.py", "tests/test_taxi_stand_measurement.py"]
    base_config = json.loads((ROOT / "config.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        if suffix == FIRST:
            continue
        folder = ROOT / "cases" / suffix
        config = dict(base_config, selected_case_id=case_id)
        write(folder / "config.json", config)
        files = [{"path": name, "content": (ROOT / name).read_text(),
                  "source": "work/" + IDENTITY + "/" + name} for name in shared]
        files.append({"path": "config.json", "content": (folder / "config.json").read_text(),
                      "source": "work/" + IDENTITY + "/cases/" + suffix + "/config.json"})
        construction = {
            "case_id": case_id, "cell_id": "C378245", "law_id": "LVMC-11-60-040",
            "actor": "taxi_driver", "entrypoint": "runner.py",
            "recording_description": case["recording_description"],
            "measurement_plan": {"stand": "Original source-hashed taxi footprint and reviewed stand boundary",
                                 "passenger": "Independent actual passenger exchange and expeditiousness review",
                                 "other_regulations": "Independent applicable other-rule source review"},
            "static_checks": ["exact selected case/config", "original site SHA-256 before Native import",
                              "900 synchronized frames and four camera views"],
            "mechanisms": ["reviewed original Native map and designated stand site",
                           "four synchronized RGB cameras", "saved taxi body and velocity samples"],
            "termination_rules": ["stop at 900 Native ticks", "fail on source or camera mismatch"],
            "files": files,
        }
        path = folder / "construction.json"
        write(path, construction)
        manifest["cases"].append({"case_id": case_id, "kind": "delivery",
                                  "construction": "cases/" + suffix + "/construction.json",
                                  "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write(manifest_path, manifest)


if __name__ == "__main__":
    build()
    print("six exact taxi constructions indexed")
