"""Make a distinct source-bound controller fallback per exact rider-formation case."""

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
        raise ValueError("four selected exact rider-formation cases required")
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
        # Keep exact rider count, exclusive-use designation, routes, sensors and evidence fixed.
        config["control_profile"] = {"speed_scale": .9}
        configs[0]["content"] = json.dumps(config, indent=2) + "\n"
        fallback = HERE / ("construction-fallback1-" + suffix + ".json")
        write(fallback, construction)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Native riders may spread longitudinally or fail to maintain side-by-side formation; a modest speed-scale adjustment preserves the reviewed rider identities, route and surface designation."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": fallback.name,
            "construction_sha256": sha(fallback),
            "trigger": {"source": "original 900-frame separate rider positions and speeds",
                        "metric": "maximum longitudinal rider separation and route occupancy",
                        "failure_condition": "riders do not maintain the planned physical formation or leave the surveyed surface"},
            "changed_knobs": ["bicycle speed scale: 0.9"]}]
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("built exact rider-formation fallbacks:", build())
