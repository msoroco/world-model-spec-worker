"""Predeclare a bounded controller-gain alternative for each physical case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        primary_path = ROOT / entry["construction"]
        if sha(primary_path) != entry["construction_sha256"]:
            raise ValueError("primary arrow construction changed")
        primary = json.loads(primary_path.read_text())
        fallback = json.loads(primary_path.read_text())
        configs = [f for f in fallback["files"] if f["path"] == "config.json"]
        if len(configs) != 1:
            raise ValueError("exact arrow bundle needs one config")
        config = json.loads(configs[0]["content"])
        if config.get("controller_gain") != 1.0:
            raise ValueError("primary reviewed adapter gain changed")
        config["controller_gain"] = 0.75
        configs[0]["content"] = json.dumps(config, indent=2) + "\n"
        if (fallback["recording_description"] != primary["recording_description"] or
                {f["path"] for f in fallback["files"]} !=
                {f["path"] for f in primary["files"]}):
            raise ValueError("fallback altered recording contract or file inventory")
        path = ROOT / ("fallback-" + suffix + "-construction.json")
        path.write_text(json.dumps(fallback, indent=2) + "\n")
        entry["candidates"] = [{
            "id": "fallback1", "construction": path.name,
            "construction_sha256": sha(path),
            "changed_knobs": ["reviewed Native adapter controller_gain: 1.0 to 0.75"],
            "trigger": {"source": "selected saved physical_checks.maneuver",
                        "metric": "measured completion status after full original capture",
                        "failure_condition": "not_met or unverified after a source-complete primary attempt"},
            "risk_note": "Only a bounded control response changes; original site, law, case and recordings remain fixed."}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("authored", build(), "controller alternatives")
