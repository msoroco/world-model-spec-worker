"""Build one camera-view fallback per exact C157964 officer case."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest-draft.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        primary_path = ROOT / entry["construction"]
        if sha(primary_path) != entry["construction_sha256"]:
            raise ValueError("Primary officer source changed before fallback")
        construction = json.loads(primary_path.read_text())
        configs = [item for item in construction["files"] if item["path"] == "config.json"]
        if len(configs) != 1:
            raise ValueError("One exact officer source configuration required")
        config = json.loads(configs[0]["content"])
        if config["selected_case_id"] != entry["case_id"]:
            raise ValueError("Officer fallback changed exact case")
        approach = config["camera_mounts"]["approach"]["pose"]
        corner = config["camera_mounts"]["reference_corner"]["pose"]
        approach["location"]["z"] = 2.0
        approach["rotation"]["pitch"] = -4.0
        corner["location"]["z"] = 9.0
        corner["rotation"]["pitch"] = -25.0
        configs[0]["content"] = json.dumps(config, indent=2, allow_nan=False) + "\n"
        suffix = entry["case_id"].split("__")[-1]
        path = ROOT / (suffix + "-fallback1-construction.json")
        path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
        source = "original approach and reference_corner camera frames at ego entry"
        metric = "source-reviewed officer/sign visibility and nearest-view coverage"
        failure = "The officer, erected sign, or through-highway view is outside or obscured in the original camera frames."
        entry["candidates"] = [{"id": "fallback1", "construction": path.name,
            "construction_sha256": sha(path),
            "trigger": {"source": source, "metric": metric,
                        "failure_condition": failure},
            "changed_knobs": ["Raise and lower the look angle of the ego approach camera",
                              "Raise and tilt the fixed reference-corner camera"]}]
    MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"cases": len(result["cases"]),
                      "fallbacks": sum(len(entry["candidates"]) for entry in result["cases"])}))
