"""Author one risk-triggered engineering fallback for every linked parking case."""

import hashlib
import json
from pathlib import Path

from comparison_audit import CASES


ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def author():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        primary = json.loads((ROOT / entry["construction"]).read_text(encoding="utf-8"))
        fallback = json.loads(json.dumps(primary))
        for file in fallback["files"]:
            if file["path"] == "native_parking.py":
                file.pop("source", None)
                source = file["content"]
                if "\"brake\": 0.65" not in source or "0.28 if speed_mps" not in source:
                    raise ValueError("primary controller changed; review fallback tuning")
                file["content"] = source.replace('"brake": 0.65', '"brake": 0.85').replace(
                    "0.28 if speed_mps", "0.20 if speed_mps")
            if file["path"] == "tests/test_bundle.py":
                file.pop("source", None)
                file["content"] = file["content"].replace(
                    'control(1, 5, "approach", "stop")["brake"], 0.65',
                    'control(1, 5, "approach", "stop")["brake"], 0.85')
        path = ROOT / ("fallback-" + suffix + "-construction.json")
        write(path, fallback)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry["candidate_risk"] = {"status": "physical",
            "reason": "Observed braking may overshoot or straddle the source-designated boundary before stationary frames; alternate lower approach throttle and stronger brake preserve the exact footprint and conduct target."}
        entry["candidates"] = [{"id": "fallback1", "construction": path.name,
            "construction_sha256": digest,
            "trigger": {"source": "parking-history.jsonl",
                        "metric": "stationary_requested_footprint_frames and last body footprint",
                        "failure_condition": "No stationary body wholly in the requested place relation after the primary approach, or boundary straddling at halt"},
            "changed_knobs": ["approach throttle 0.28 to 0.20",
                              "approach braking command 0.65 to 0.85"]}]
    write(manifest_path, manifest)


if __name__ == "__main__":
    author()
