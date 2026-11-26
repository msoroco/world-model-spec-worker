"""Make a distinct source-bound controller fallback per exact bus speed case."""

import hashlib
import json
from pathlib import Path

from package_spec import AID

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("fallback return exceeds 2 MiB")


def build():
    manifest_path = HERE / "execution-manifest.selected-draft.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("assignment_id") != AID or len(manifest["cases"]) != 4:
        raise ValueError("four selected exact school-bus cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        primary = HERE / entry["construction"]
        if sha(primary) != entry["construction_sha256"]:
            raise ValueError("primary source changed")
        construction = json.loads(primary.read_text())
        configs = [item for item in construction["files"] if item["path"] == "config.json"]
        if len(configs) != 1:
            raise ValueError("one exact config required")
        config = json.loads(configs[0]["content"])
        if config["selected_case_id"] != entry["case_id"]:
            raise ValueError("wrong fallback case")
        config["candidate_id"] = "fallback1"
        # Keep exact 54/55/56 mph target, trip, route, sensors and evidence fixed.
        config["control_profile"] = {"accel_gain": .30}
        configs[0]["content"] = json.dumps(config, indent=2) + "\n"
        fallback = HERE / ("construction-fallback1-" + suffix + ".json")
        write(fallback, construction)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Original school bus may not attain its requested speed during the source-verified 900-metre route; controller gain adjustment can improve acceleration while preserving exact target, trip status and geometry."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": fallback.name,
            "construction_sha256": sha(fallback),
            "trigger": {"source": "original 900-frame Native bus velocity and surveyed route readback",
                        "metric": "realized target speed during source-confirmed transport interval and route containment",
                        "failure_condition": "actual bus fails to reach requested speed within tolerance or remain on reviewed route"},
            "changed_knobs": ["controller acceleration gain: 0.30"]}]
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("built exact school-bus fallbacks:", build())
