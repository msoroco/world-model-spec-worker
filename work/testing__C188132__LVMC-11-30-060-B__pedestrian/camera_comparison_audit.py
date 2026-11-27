"""Bind selected original camera construction before C188132 pair audits."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

from overpass_source import audit_pair

ROOT = Path(__file__).resolve().parent
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def selected_plan(attempt, case_id):
    """Read the selected, source-hashed Native camera function and exact scene."""
    attempt = Path(attempt).resolve()
    manifest_path = ROOT / "execution-manifest.json"
    manifest = read(manifest_path)
    selection = read(attempt / "candidate-selection.json")
    if (selection.get("format") != "worker-candidate-selection" or
            selection.get("case_id") != case_id or
            selection.get("manifest_sha256") != sha(manifest_path)):
        raise ValueError("original camera candidate selection differs from manifest")
    matches = [row for row in manifest["cases"] if row["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("exact camera comparison case missing or duplicated")
    row = matches[0]
    candidates = ([{"id": "primary", "construction": row["construction"],
                    "construction_sha256": row["construction_sha256"]}]
                  + row.get("candidates", []))
    selected = [item for item in candidates if item["id"] == selection.get("candidate_id")]
    if (len(selected) != 1 or
            selected[0]["construction_sha256"] != selection.get("construction_sha256")):
        raise ValueError("selected original camera construction differs")
    source = ROOT / selected[0]["construction"]
    if sha(source) != selected[0]["construction_sha256"]:
        raise ValueError("selected original camera construction hash differs")
    construction = read(source)
    if read(attempt / "construction.json") != construction:
        raise ValueError("original attempt construction differs")
    files = {item["path"]: item["content"] for item in construction["files"]}
    if "native_capture.py" not in files or "scene.json" not in files:
        raise ValueError("original camera source or scene missing")
    camera_source = files["native_capture.py"]
    scene_source = files["scene.json"]
    if ((attempt / "native_capture.py").read_text(encoding="utf-8") != camera_source or
            (attempt / "scene.json").read_text(encoding="utf-8") != scene_source):
        raise ValueError("original camera source or scene differs")
    tree = ast.parse(camera_source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "camera_placements"]
    if len(functions) != 1:
        raise ValueError("original camera placement function missing or duplicated")
    namespace = {"__builtins__": {"ValueError": ValueError, "range": range}, "math": math}
    exec(compile(ast.Module(body=functions, type_ignores=[]),
                 "<selected-original-camera>", "exec"), namespace)
    plan = namespace["camera_placements"](json.loads(scene_source))
    if not isinstance(plan, dict) or set(plan) != CAMERAS:
        raise ValueError("four selected original camera views required")
    return plan


def check_selected_cameras(first, second, comparison):
    plan = read(ROOT / "case-plan.json")
    rows = [row for row in plan["comparisons"]
            if row["comparison_id"] == comparison]
    if len(rows) != 1 or len(rows[0]["case_ids"]) != 2:
        raise ValueError("camera comparison pair missing or duplicated")
    case_ids = rows[0]["case_ids"]
    first_plan = selected_plan(first, case_ids[0])
    second_plan = selected_plan(second, case_ids[1])
    if first_plan != second_plan:
        raise ValueError("comparison selected candidates changed fixed camera positions")
    return {"case_ids": case_ids, "camera_plan_sha256": hashlib.sha256(
        json.dumps(first_plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--comparison", required=True,
                        choices=("entry_timing", "designated_exception"))
    parser.add_argument("--first-processing", required=True)
    parser.add_argument("--second-processing", required=True)
    args = parser.parse_args()
    binding = check_selected_cameras(args.first, args.second, args.comparison)
    result = audit_pair(args.first, args.second, args.comparison,
                        first_processing=args.first_processing,
                        second_processing=args.second_processing)
    result["selected_camera_binding"] = binding
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
