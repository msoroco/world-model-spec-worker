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
    if manifest.get("assignment_id") != AID or len(manifest["cases"]) != 14:
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
        # These are engineering controller settings. No legal threshold or
        # lane-availability conclusion is inferred from either value.
        config["control_profile"] = {"target_speed_mps": 8.0, "lookahead_m": 6.0,
                                     "lane_entry_gain": 0.75}
        configs[0]["content"] = json.dumps(config, indent=2) + "\n"
        fallback = HERE / ("construction-fallback1-" + suffix + ".json")
        write(fallback, construction)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Native rider and ego motion may outrun four-view framing or miss the intended lane entry; source review after first capture determines whether slower motion and gentler lane entry are needed."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": fallback.name,
            "construction_sha256": sha(fallback),
            "trigger": {"source": "original 900-frame actor trace and four camera source audit",
                        "metric": "sampled lane entry, full-body pass and rider visibility",
                        "failure_condition": "planned lane entry or rider visibility is absent in the original capture"},
            "changed_knobs": ["target_speed_mps: 8.0", "lookahead_m: 6.0",
                              "lane_entry_gain: 0.75"]}]
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("built exact physical fallbacks:", build())
