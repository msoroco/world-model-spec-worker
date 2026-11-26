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
    if manifest.get("assignment_id") != AID or len(manifest["cases"]) != 7:
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
        adapters = [item for item in construction["files"]
                    if item["path"] == "signal_carla_adapter.py"]
        if len(adapters) != 1:
            raise ValueError("one source-gated Native adapter required")
        old = "        if self.behavior == \"stop_before_entry\":\n"
        new = "        target_speed *= 0.75  # physical phase-entry bracket fallback\n" + old
        if adapters[0]["content"].count(old) != 1:
            raise ValueError("Native controller tuning point changed")
        adapters[0]["content"] = adapters[0]["content"].replace(old, new)
        fallback = HERE / ("construction-fallback1-" + suffix + ".json")
        write(fallback, construction)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Original 20 Hz signal phase and ego body-entry frames may straddle the requested bracket; slower approach can shift the physical entry without changing the signal rule."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": fallback.name,
            "construction_sha256": sha(fallback),
            "trigger": {"source": "original 900-frame signal packet, body geometry and four camera source audit",
                        "metric": "selected facing phase at surveyed front-body entry frame",
                        "failure_condition": "the planned entry-phase bracket is absent in the original capture"},
            "changed_knobs": ["controller target speed scale: 0.75"]}]
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("built exact physical fallbacks:", build())
