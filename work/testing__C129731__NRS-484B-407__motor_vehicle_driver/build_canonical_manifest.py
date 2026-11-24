"""Bind exact primary and fallback CPU proofs into the selected manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    tests = {row["log"]: row for row in result["tests"]}
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    selected_ids = {case["case_id"] for case in proposal["cases"]
                    if case["target_type"] != "baseline"}
    manifest["cases"] = [entry for entry in manifest["cases"]
                         if entry["case_id"] in selected_ids]
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        offline = tests["cpu-offline-" + suffix + ".log"]
        if offline["exit_code"] or sha(HERE / offline["log"]) != offline["sha256"]:
            raise ValueError("Primary offline proof changed: " + suffix)
        entry["kind"] = "delivery"
        entry["offline"] = {"command": offline["command"], "exit_code": 0,
                            "log": offline["log"],
                            "log_sha256": offline["sha256"],
                            "construction_sha256": entry["construction_sha256"]}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        entry["acquisition"].update({
            "road_geometry": {
                "entrypoint": "native_sight_capture.py", "method": "capture",
                "evidence": "Original road_geometry.json and derived channels/road_geometry.json",
            },
            "approaching_vehicle_routes": {
                "entrypoint": "native_sight_capture.py", "method": "capture",
                "evidence": "Original approach_motion.json and derived channels/approaching_vehicle_routes.json",
            },
            "frame_map": {
                "entrypoint": "native_sight_capture.py", "method": "capture",
                "evidence": "Original 900-frame frame_map.json and derived channels/frame_map.json",
            },
        })
        physical = entry.get("physical_preparation", {})
        if sha(HERE / physical["receipt"]) != physical["sha256"]:
            raise ValueError("Physical preparation changed: " + suffix)
        for candidate in entry["candidates"]:
            if candidate["id"] != "fallback1":
                raise ValueError("Unexpected fallback for " + suffix)
            spec = candidate.get("compatibility", {})
            if (not all(spec.get(key) for key in
                        ("receipt", "sha256", "log", "negative_log")) or
                    sha(HERE / spec["receipt"]) != spec["sha256"]):
                raise ValueError("Fallback compatibility proof missing: " + suffix)
    (HERE / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print("Canonical three-case manifest", sha(HERE / "execution-manifest.json"))


if __name__ == "__main__":
    build()
