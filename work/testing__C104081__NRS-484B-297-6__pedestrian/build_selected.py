"""Materialize source-gated primary and walking-speed fallback constructions.

The fixture recipes remain diagnostic. The selected runner requires a reviewed
original site and live OpenDRIVE equality before any Native actor mutation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_offline_draft import HERE, AID, RUNNER, TEST, SOURCE_FILES, RECORDING_DESCRIPTION

SOURCE_FILES = SOURCE_FILES + ("original_review.py",)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> None:
    plan_raw = (HERE / "case-plan.json").read_text()
    plan = json.loads(plan_raw)
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    primary_runner = RUNNER.replace("diagnostic sidewalk-bypass bundle passed:",
                                    "source-gated sidewalk-bypass bundle passed:")
    entries = []
    for case, old in zip(plan["cases"], draft["cases"]):
        case_id = case["case_id"]
        if old["case_id"] != case_id:
            raise ValueError("exact case ordering changed")
        suffix = case_id.removeprefix(AID + "__")
        constructions = []
        for candidate, speed in (("primary", 1.4), ("fallback1", 1.2)):
            old_construction = json.loads((HERE / old["construction"]).read_text())
            config = json.loads(next(item["content"] for item in old_construction["files"]
                                     if item["path"] == "config.json"))
            config["diagnostic_only"] = False
            config["requested_speed_mps"] = speed
            config["source_gate"] = "reviewed_original_site_and_live_opendrive_sha256"
            files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
            files.update({"runner.py": primary_runner, "case-plan.json": plan_raw,
                          "config.json": json.dumps(config, indent=2) + "\n",
                          "tests/test_bundle.py": TEST})
            construction = dict(old_construction)
            construction.pop("diagnostic_only", None)
            construction["files"] = [{"path": name, "content": content}
                                     for name, content in files.items()]
            construction["source_gate"] = config["source_gate"]
            filename = f"construction-selected-{suffix}.json" if candidate == "primary" \
                else f"construction-fallback1-{suffix}.json"
            path = HERE / filename
            write(path, construction)
            constructions.append((candidate, filename, sha(path)))
        selected = dict(old)
        selected["construction"] = constructions[0][1]
        selected["construction_sha256"] = constructions[0][2]
        selected["candidate_risk"] = {
            "status": "physical",
            "reason": "The live pedestrian can overshoot a surveyed route waypoint at the requested 1.4 m/s. A predeclared 1.2 m/s walking request is a slower engineering fallback, selected only after measured source-complete waypoint overshoot; the path, source observations, four cameras, duration and exact comparison variable remain unchanged."}
        selected["candidates"] = [{"id": "fallback1", "construction": constructions[1][1],
            "construction_sha256": constructions[1][2],
            "changed_knobs": ["requested pedestrian walking speed: 1.4 to 1.2 m/s"],
            "trigger": {"source": "sealed original pedestrian route samples",
                        "metric": "maximum observed cross-track or waypoint overshoot in metres",
                        "failure_condition": "source-complete primary misses a surveyed waypoint by more than 0.25 m"}}]
        selected["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                      "host_env_var": "CARLA_HOST",
                                      "port_env_var": "CARLA_PORT",
                                      "site_root_env_var": "SCENARIO_PEDESTRIAN_SOURCE_ROOT"}
        selected.pop("diagnostic_proof", None)
        entries.append(selected)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(HERE.parents[1] / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    write(HERE / "execution-manifest.json", manifest)
    first = json.loads((HERE / entries[0]["construction"]).read_text())
    config = json.loads(next(item["content"] for item in first["files"]
                             if item["path"] == "config.json"))
    config["supported_case_ids"] = [item["case_id"] for item in entries]
    config["cameras"] = [
        {"name": name, "width": width, "height": height,
         "pose_strategy": "reviewed original C104081 source camera pose",
         "fov_deg": 90}
        for name, width, height in (("overview", 1920, 1080),
                                    ("approach", 1280, 720),
                                    ("reference_corner", 1280, 720),
                                    ("driver_reference", 1280, 720))]
    write(HERE / "config.json", config)
    (HERE / "runner.py").write_text(primary_runner)
    root = dict(first)
    root["files"] = [{"path": item["path"],
                      "content": (HERE / item["path"]).read_text() if
                      item["path"] == "runner.py" else
                      (HERE / "config.json").read_text() if item["path"] == "config.json"
                      else item["content"]} for item in first["files"]]
    root["measurement_plan"] = {"cases": config["supported_case_ids"],
                                "source": "sealed saved source measurements"}
    root["static_checks"] = ["reviewed site and live OpenDRIVE hash",
                             "20 Hz original frame join", "four synchronized cameras"]
    root["termination_rules"] = ["900 original frames", "measured route completion"]
    root["mechanisms"] = ["measured pedestrian walking controller",
                          "source-bound sidewalk obstruction and traffic roster"]
    write(HERE / "construction.json", root)
    print("built", len(entries), "source-gated cases with one speed fallback each")


if __name__ == "__main__":
    build()
