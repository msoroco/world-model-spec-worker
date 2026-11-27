"""Prepare a distinct surveyed-vehicle fallback for each selected hydrant case."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    alternatives = []
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        suffix = case["case_id"].split("__")[-1]
        source = HERE / ("selected-" + suffix + "-construction.json")
        alternate = json.loads(source.read_text())
        config = next(item for item in alternate["files"] if item["path"] == "config.json")
        configuration = json.loads(config["content"])
        if configuration["vehicle_blueprint"] != "vehicle.tesla.model3":
            raise ValueError("Primary vehicle source changed")
        configuration["vehicle_blueprint"] = "vehicle.lincoln.mkz_2020"
        config["content"] = json.dumps(configuration, indent=2) + "\n"
        alternate["status"] = "selected_fallback_cpu_construction_unverified"
        path = HERE / ("selected-" + suffix + "-fallback1-construction.json")
        path.write_text(json.dumps(alternate, indent=2) + "\n")
        alternatives.append({"case_id": case["case_id"], "id": "fallback1",
            "construction": "native/" + path.name,
            "construction_sha256": sha(path),
            "trigger": {"source": "original hydrant-trace.jsonl and hydrant_survey.json",
                        "metric": "closest body-to-hydrant clearance and Native actor spawn status",
                        "failure_condition": "Primary vehicle cannot spawn at surveyed parking location or measured clearance misses requested bracket"},
            "changed_knobs": ["vehicle blueprint Tesla Model 3 to Lincoln MKZ 2020"]})
    path = ROOT / "selected-fallback-prepared.json"
    path.write_text(json.dumps({"format": "worker-fallback-preparation-v1",
                                "alternatives": alternatives}, indent=2) + "\n")
    print(json.dumps({"fallbacks": len(alternatives), "index_sha256": sha(path)}))


if __name__ == "__main__":
    main()
