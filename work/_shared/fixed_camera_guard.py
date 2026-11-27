"""Reject mixed camera placements before two selected comparison audits.

This guard reads the original candidate receipt and exact construction. It is a
CPU source check, not a claim that physical cameras captured useful pixels.
"""

import ast
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENTS = {
    "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator":
        ("POSITIONS", "module"),
    "testing__C188132__LVMC-11-30-060-B__pedestrian":
        ("sites", "camera_placements"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def literal_assignment(source, name, scope):
    tree = ast.parse(source)
    nodes = tree.body
    if scope != "module":
        functions = [node for node in nodes if isinstance(node, ast.FunctionDef)
                     and node.name == scope]
        if len(functions) != 1:
            raise ValueError("camera placement function missing or duplicated")
        nodes = functions[0].body
    matches = [node.value for node in nodes if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name
                       for target in node.targets)]
    if len(matches) != 1:
        raise ValueError("camera placement table missing or duplicated")
    value = ast.literal_eval(matches[0])
    if not isinstance(value, dict) or set(value) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four fixed camera positions required")
    if scope == "camera_placements":
        targets = [node.value for node in nodes if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "target"
                           for target in node.targets)]
        if len(targets) != 1:
            raise ValueError("camera target missing or duplicated")
        return {"sites": value, "target": ast.literal_eval(targets[0])}
    return value


def effective_plan(source, assignment, scene=None):
    """Evaluate only the source-hashed camera function and its literal plan."""
    tree = ast.parse(source)
    if "C10307" in assignment:
        definitions = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "POSITIONS"
                               for target in node.targets)]
        definitions += [node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "camera_transform"]
        if len(definitions) != 2:
            raise ValueError("original camera transform definition missing or duplicated")
        namespace = {"__builtins__": {}}
        exec(compile(ast.Module(body=definitions, type_ignores=[]), "<camera-plan>", "exec"), namespace)

        class FakeCarla:
            @staticmethod
            def Location(**values):
                return values

            @staticmethod
            def Rotation(**values):
                return values

            @staticmethod
            def Transform(location, rotation):
                return {"location": location, "rotation": rotation}

        return {name: namespace["camera_transform"](FakeCarla, name)
                for name in ("overview", "approach", "reference_corner", "driver_reference")}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "camera_placements"]
    if len(functions) != 1 or not isinstance(scene, dict):
        raise ValueError("original camera placement function or scene missing")
    namespace = {"__builtins__": {"range": range, "ValueError": ValueError}, "math": math}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<camera-plan>", "exec"), namespace)
    result = namespace["camera_placements"](scene)
    if not isinstance(result, dict) or set(result) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("effective four-camera plan missing")
    return result


def camera_plan(root, assignment, case_id, attempt):
    name, scope = ASSIGNMENTS[assignment]
    manifest_path = root / "work" / assignment / "execution-manifest.json"
    manifest = read(manifest_path)
    receipt = read(attempt / "candidate-selection.json")
    if receipt.get("format") != "worker-candidate-selection" or receipt.get("case_id") != case_id or \
            receipt.get("manifest_sha256") != sha(manifest_path):
        raise ValueError("candidate selection is missing or differs from selected manifest")
    matches = [row for row in manifest["cases"] if row["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("exact comparison case missing or duplicated")
    row = matches[0]
    candidates = ([{"id": "primary", "construction": row["construction"],
                    "construction_sha256": row["construction_sha256"]}]
                  + row.get("candidates", []))
    selected = [item for item in candidates if item["id"] == receipt.get("candidate_id")]
    if len(selected) != 1 or receipt.get("construction_sha256") != selected[0]["construction_sha256"]:
        raise ValueError("selected candidate construction differs")
    construction_path = manifest_path.parent / selected[0]["construction"]
    if sha(construction_path) != selected[0]["construction_sha256"]:
        raise ValueError("selected construction hash differs")
    construction = read(construction_path)
    if read(attempt / "construction.json") != construction:
        raise ValueError("original attempt construction differs")
    camera_files = [item["content"] for item in construction["files"]
                    if item["path"] == "native_capture.py"]
    if len(camera_files) != 1 or (attempt / "native_capture.py").read_text(encoding="utf-8") != camera_files[0]:
        raise ValueError("original camera implementation differs")
    declared = literal_assignment(camera_files[0], name, scope)
    scene = None
    if "C188132" in assignment:
        scene_files = [item["content"] for item in construction["files"]
                       if item["path"] == "scene.json"]
        if len(scene_files) != 1 or (attempt / "scene.json").read_text(encoding="utf-8") != scene_files[0]:
            raise ValueError("original camera scene differs")
        scene = json.loads(scene_files[0])
    return {"declared": declared,
            "effective": effective_plan(camera_files[0], assignment, scene)}


def check(root, identifier, first, second):
    assignment, comparison_id = identifier.split("::", 1)
    if assignment not in ASSIGNMENTS:
        return
    plan = read(root / "work" / assignment / "case-plan.json")
    rows = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    if len(rows) != 1 or len(rows[0]["case_ids"]) != 2:
        raise ValueError("fixed-camera comparison pair missing or duplicated")
    plans = [camera_plan(root, assignment, case, Path(attempt))
             for case, attempt in zip(rows[0]["case_ids"], (first, second))]
    if plans[0] != plans[1]:
        raise ValueError("comparison selected candidates changed fixed camera positions")
