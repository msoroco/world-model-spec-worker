"""Materialize the representative exact alley case at the canonical root."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def materialize() -> None:
    original = json.loads((HERE / "construction-steady_travel.json").read_text())
    files = {row["path"]: row["content"] for row in original["files"]}
    config = json.loads(files["config.json"])
    config["supported_case_ids"] = [
        HERE.name + "__steady_travel", HERE.name + "__steering_variation"]
    config["native_camera_ids"] = list(config["cameras"])
    names = ("overview", "approach", "reference_corner", "driver_reference")
    sizes = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    strategies = (
        "source-reviewed alley trajectory and adjacent parking access aisle",
        "ego entry into the source-reviewed alley route",
        "contrasting access-aisle stripes and body separation",
        "original driver and vehicle reference throughout operation",
    )
    config["cameras"] = [
        {"name": name, "width": size[0], "height": size[1],
         "fov_deg": 75, "pose_strategy": strategy}
        for name, size, strategy in zip(names, sizes, strategies)]
    runner = files["runner.py"].replace(
        'if config["cameras"] != list(CAMERAS):',
        'if config["native_camera_ids"] != list(CAMERAS) or '
        '[item["name"] for item in config["cameras"]] != '
        '["overview", "approach", "reference_corner", "driver_reference"]:')
    if runner == files["runner.py"]:
        raise ValueError("canonical runner camera check was not updated")
    files["runner.py"] = runner
    files["config.json"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
    for name in ("runner.py", "config.json", "tests/test_bundle.py"):
        path = HERE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(files[name])
    root = dict(original)
    root["diagnostic_only"] = True
    root["measurement_plan"] = {
        "case_id": original["case_id"], "procedure": "saved_finalizer.py",
        "source_packets": ["reviewed_original_alley_site", "operation.jsonl",
                           "camera-frame-map.jsonl", "four_original_camera_png_streams"],
        "legal_judgment": "unresolved", "original_frames": 900}
    root["static_checks"] = [
        "exact law/cell/actor identity", "reviewed original alley and access-aisle packet",
        "900 joined 20 Hz Native frames", "four original camera streams"]
    root["termination_rules"] = [
        "stop after 900 original frames or fail on missing source",
        "retain failed Native attempt and require independent restoration receipt"]
    root["mechanisms"] = [
        "source-reviewed alley route and adjacent designated parking access aisle",
        "original Native ego and original four-camera acquisition",
        "saved-only source audit; interior attention and legal judgment unresolved"]
    root["files"] = [{"path": name, "content": content} for name, content in files.items()]
    write(HERE / "construction.json", root)
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if plan.get("selected_branch") not in (None, "Vehicle operation on an alley route"):
        raise ValueError("selected witness branch differs")
    plan["selected_branch"] = "Vehicle operation on an alley route"
    if plan.get("observations") and isinstance(plan["observations"][0], str):
        plan["observation_notes"] = plan["observations"]
        plan["observations"] = [
            {"name": row["name"], "unit": row["unit"], "mandatory": True,
             "evidence": row["method"]}
            for row in original["recording_description"]["channels"]]
    interior = next(row for row in original["recording_description"]["context_inputs"]
                    if row["name"] == "original_eyes_off_road_duration_s")
    plan["observations"] = [row for row in plan["observations"]
                            if row.get("name") != interior["name"]]
    for selected in plan["cases"]:
        context = selected["recording_description"]["context_inputs"]
        if not any(row["name"] == interior["name"] for row in context):
            context.append(dict(interior))
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "ego alley trajectory and access-aisle context",
             "interval": "full 45-second original operation"},
            {"view": "approach", "subject": "ego body and alley approach",
             "interval": "full 45-second original operation"},
            {"view": "reference_corner", "subject": "marked parking access aisle",
             "interval": "full 45-second original operation"},
            {"view": "driver_reference", "subject": "driver and ego reference",
             "interval": "full 45-second original operation"}],
    }
    write(plan_path, plan)
    print("canonical root bundle materialized for first selected exact case")


if __name__ == "__main__":
    materialize()
