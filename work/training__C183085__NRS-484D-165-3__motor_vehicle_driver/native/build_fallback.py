"""Create a source-preserving alternate vehicle for a surveyed shoulder spawn failure."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = json.loads((ROOT / "selected-shoulder-draft-manifest.json").read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        original = json.loads((ROOT / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(original))
        for item in fallback["files"]:
            if item["path"] == "config.json":
                config = json.loads(item["content"])
                assert config["vehicle_blueprint"] == "vehicle.tesla.model3"
                config["vehicle_blueprint"] = "vehicle.lincoln.mkz_2020"
                item["content"] = json.dumps(config, indent=2) + "\n"
        path = NATIVE / ("selected-" + suffix + "-fallback1-construction.json")
        write(path, fallback)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "A surveyed shoulder pose may not fit the primary vehicle body",
        }
        entry["candidates"] = [{
            "case_id": entry["case_id"], "id": "fallback1",
            "construction": str(path.relative_to(ROOT)),
            "construction_sha256": sha(path),
            "trigger": {
                "source": "original Native actor spawn result and shoulder_lighting_survey.json",
                "metric": "surveyed shoulder actor spawn status",
                "failure_condition": "Primary Tesla Model 3 cannot spawn at the surveyed shoulder pose",
            },
            "changed_knobs": ["vehicle blueprint Tesla Model 3 to Lincoln MKZ 2020"],
        }]
        print(suffix, sha(path), flush=True)
    path = ROOT / "selected-fallback-compat-manifest.json"
    write(path, manifest)
    print("manifest", sha(path))


if __name__ == "__main__":
    main()
