"""Materialize exact CPU diagnostic route variants for the sidewalk branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from corridor_construction import compare_authored_routes, make_scene, measure_original, request_next_target
from saved_measurement import measure_saved
from corridor_map import map_bytes, verify_candidate_map


def body(x, y):
    return [[x-.2, y-.25], [x+.2, y-.25], [x+.2, y+.25], [x-.2, y+.25]]


def build(root):
    root = Path(root)
    map_path = root / "candidate-corridor.xodr"
    map_path.write_bytes(map_bytes())
    map_result = verify_candidate_map(map_path)
    prefix = "testing__C143766__LVMC-11-30-090__pedestrian__"
    cases = {}
    scenes = {}
    for band in ("roadway", "sidewalk", "shoulder"):
        case_id = prefix + band + "_walk"
        scene = make_scene(case_id, band)
        scenes[band] = scene
        folder = root / "cases" / (band + "_walk")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "scene.json"
        path.write_text(json.dumps(scene, indent=2) + "\n")
        frames = [{"frame": i, "body_xy_m": body(2+i*13, scene["pedestrian_route_xy_m"][0][1])}
                  for i in range(3)]
        measurement = measure_original(scene, frames)
        history_path = folder / "diagnostic-body-history.jsonl"
        history_path.write_text("".join(json.dumps({"case_id": case_id, **frame}) + "\n" for frame in frames))
        sources = {"format": "c143766-original-pedestrian-sources-v1",
                   "scene": {"path": str(path.relative_to(root)),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                   "map": {"path": map_path.name, "sha256": map_result["map_sha256"]},
                   "body_history": {"path": str(history_path.relative_to(root)),
                                    "sha256": hashlib.sha256(history_path.read_bytes()).hexdigest()}}
        source_path = folder / "diagnostic-source-manifest.json"
        source_path.write_text(json.dumps(sources, indent=2) + "\n")
        saved = measure_saved(root, source_path)
        if saved["measurement"] != measurement:
            raise ValueError("saved measurement differs from authored fixture")
        request = request_next_target(scene, 2, scene["pedestrian_route_xy_m"][0][1])
        cases[case_id] = {"scene": str(path.relative_to(root)),
                          "scene_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "diagnostic_source_manifest": str(source_path.relative_to(root)),
                          "diagnostic_source_manifest_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                          "measurement": saved["measurement"], "first_walker_request": request}
    comparisons = {
        "roadway_vs_sidewalk": compare_authored_routes(scenes["roadway"], scenes["sidewalk"], True),
        "roadway_vs_shoulder": compare_authored_routes(scenes["roadway"], scenes["shoulder"], True),
    }
    return {"format": "c143766-corridor-diagnostic-v1", "map": map_result,
            "cases": cases,
            "comparisons": comparisons,
            "limitations": "Authored corridor and synthetic full-body samples only; sidewalk purpose, municipal map, roadway/shoulder definitions and actual movement require source review."}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    (root / "corridor-diagnostic-proof.json").write_text(json.dumps(build(root), indent=2) + "\n")
