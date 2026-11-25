"""Bind all nine exact rail-stop constructions to the frozen case plan.

This builder writes source text only beneath its owning assignment. The
materialized scripts use an original site packet at Native execution time.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MODULES = ("runner.py", "native_construction.py", "native_control.py",
           "native_camera.py", "native_capture.py", "rail_stop_audit.py",
           "analysis.py", "comparison_audit.py", "case-plan.json")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def construct(case: dict, plan: dict, destination: Path) -> None:
    config = {
        "assignment_id": ASSIGNMENT, "law_id": plan["law_id"],
        "cell_id": plan["cell_id"], "actor": plan["actor"],
        "selected_case_id": case["case_id"],
        "supported_case_ids": [row["case_id"] for row in plan["cases"]],
        "case": case, "rate_hz": 20, "frame_count": 900, "duration_s": 45,
        "cameras": [{"name": name, "width": width, "height": height,
                     "pose_strategy": "source-reviewed original crossing pose",
                     "fov_deg": 90}
                    for name, width, height in (("overview", 1920, 1080),
                                                ("approach", 1280, 720),
                                                ("reference_corner", 1280, 720),
                                                ("driver_reference", 1280, 720))],
        "required_atoms": [], "source_packets": [],
        "recording_description": {
            "channels": [{"name": "rail_stop", "unit": "structured",
                          "method": "original Native speed, body corners and nearest rail line",
                          "time_window": "all 900 frames", "reference_frame": "original Native frame map",
                          "uncertainty": "statutory vehicle reference point and due care unresolved",
                          "sampling_rate_hz": 20},
                         {"name": "crossing_conflict_history", "unit": "structured",
                          "method": "original Native conflict actor footprint and speed when selected",
                          "time_window": "all 900 frames", "reference_frame": "original Native frame map",
                          "uncertainty": "scene conflict alone does not resolve due care",
                          "sampling_rate_hz": 20}],
            "context_inputs": [{"name": "crossing_authority", "unit": "metadata",
                                "method": "source-hashed original designation and official governing sign"}],
            "limitations": ["Diagnostic fixtures cannot prove DOT authority, actual pixels or due care."]},
        "source_gate": "reviewed designation/sign/rail/camera records and exact Native map before world mutation"}
    write_json(destination / "config.json", config)
    entries = []
    for name in (*MODULES, "config.json"):
        source = destination / name if name == "config.json" else HERE / name
        entries.append({"path": name, "source": source.relative_to(HERE.parents[1]).as_posix(),
                        "content": source.read_text(encoding="utf-8")})
    for source in sorted((HERE / "tests").glob("test*.py")):
        entries.append({"path": "tests/" + source.name,
                        "source": source.relative_to(HERE.parents[1]).as_posix(),
                        "content": source.read_text(encoding="utf-8")})
    proposal = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                "actor": plan["actor"], "case_id": case["case_id"],
                "entrypoint": "runner.py", "files": entries,
                "recording_description": config["recording_description"],
                "measurement_plan": [
                    {"name": "crossing_authority", "source": "source-hashed designation, rail, sign and original site review"},
                    {"name": "rail_stop", "source": "original 20 Hz Native speed/body/rail source and four-camera frame map"},
                    {"name": "crossing_conflict_history", "source": "original 20 Hz conflict actor body/source or recorded absence"}],
                "static_checks": ["exact case and reviewed site", "900-frame four-view profile"],
                "termination_rules": ["45 seconds at 20 Hz", "abort on missing camera or original source join"],
                "mechanisms": ["source-gated Native rail crossing",
                               "original body-to-nearest-rail measurement",
                               "independent saved-only rail audit"]}
    write_json(destination / "construction.json", proposal)


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan["assignment_id"] != ASSIGNMENT or len(plan["cases"]) != 9:
        raise ValueError("exact nine-case C202480 plan required")
    for index, case in enumerate(plan["cases"]):
        suffix = case["case_id"].removeprefix(ASSIGNMENT + "__")
        if suffix == case["case_id"]:
            raise ValueError("case ID differs from assignment")
        destination = HERE if index == 0 else HERE / "cases" / suffix
        destination.mkdir(parents=True, exist_ok=True)
        construct(case, plan, destination)
    manifest_path = HERE / "execution-manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous = {item["case_id"]: item for item in old.get("cases", [])}
    entries = []
    for index, case in enumerate(plan["cases"]):
        suffix = case["case_id"].removeprefix(ASSIGNMENT + "__")
        relative = "construction.json" if index == 0 else f"cases/{suffix}/construction.json"
        construction = HERE / relative
        entry = previous.get(case["case_id"], {})
        if entry.get("construction_sha256") != hashlib.sha256(construction.read_bytes()).hexdigest():
            entry = {}
        entry.update({"case_id": case["case_id"], "kind": "delivery",
                      "construction": relative,
                      "construction_sha256": hashlib.sha256(construction.read_bytes()).hexdigest()})
        entries.append(entry)
    # This is a draft until every offline, compatibility, semantic and delivery
    # receipt is bound. Keeping every planned case here enables exact offline.
    repo = HERE.parents[1]
    write_json(manifest_path, {"format": "worker-execution-manifest",
                               "assignment_id": ASSIGNMENT,
                               "runtime_manifest_sha256": hashlib.sha256(
                                   (repo / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                               "cases": entries})
    print(json.dumps({"assignment_id": ASSIGNMENT, "constructions": 9}))


if __name__ == "__main__":
    main()
