"""Make a distinct source-bound physical controller fallback per exact case."""

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
    if manifest.get("assignment_id") != AID or len(manifest["cases"]) != 2:
        raise ValueError("exact selected manifest required")
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
        # The fallback tunes only physical approach speed and phase timing.
        # It preserves the selected law, scene, sensors and recorded observables.
        config["control_profile"] = {"speed_scale": 0.75}
        configs[0]["content"] = json.dumps(config, indent=2) + "\n"
        fallback = HERE / ("construction-fallback1-" + suffix + ".json")
        write(fallback, construction)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Realized body clearance beside the barrier may differ from planned clearance; slower controller speed may improve steer tracking without changing law, geometry, or selected route."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": fallback.name,
            "construction_sha256": sha(fallback),
            "trigger": {"source": "original 900-frame barrier packet, body geometry and four-camera source audit",
                        "metric": "realized body-to-barrier clearance and connected passage",
                        "failure_condition": "actual body clearance or connected passage is not established in original capture"},
            "changed_knobs": ["controller target speed scale: 0.75"]}]
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("built exact physical fallbacks:", build())
