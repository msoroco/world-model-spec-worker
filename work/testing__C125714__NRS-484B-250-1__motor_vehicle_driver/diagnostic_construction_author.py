"""Build an exact-ID CPU diagnostic bundle; never assert reviewed legal context."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_builder import config, recording_description
from map_inventory import inventory


ROOT = Path(__file__).resolve().parent
CASE_VARIANTS = (("precedence", True, "yield"),
                 ("advance", True, "advance"),
                 ("other_later", False, "yield"),
                 ("opposite_straight", True, "yield"),
                 ("opposite_intends_left", True, "yield"),
                 ("opposite_makes_left", True, "yield"),
                 ("wide_same_crossing", True, "yield"))
MAP_SOURCE = ROOT / "connected-median-candidate.xodr"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    # This engineering map has declared XML junction paths. Native loading and
    # waypoint successor connectivity have NOT been tested without CARLA.
    crossing = {"crossing_id": "candidate-central-crossing-diagnostic",
                "roadway_id": "candidate-east-west-westward-segment",
                "bounds_xy_m": [-3.5, -7.0, 3.5, 7.0],
                "map_source_sha256": sha(MAP_SOURCE)}
    (ROOT / "candidate-map.xodr").write_bytes(MAP_SOURCE.read_bytes())
    write_json(ROOT / "candidate-map-inventory.json", inventory(ROOT / "candidate-map.xodr"))
    base_scene = {
        "diagnostic_only": True,
        "crossing": crossing, "ego_highway": "candidate-east-west",
        "other_highway": "candidate-north-south", "ego_approach_road_id": 10,
        "other_approach_road_id": 31,
        "ego_route_xy_m": [[-15, -5.75], [-5, -5.75], [-2, -5.75],
                           [2, -5.75], [5, -5.75], [15, -5.75]],
        "other_route_xy_m": [[0, -15], [0, -7], [0, -3],
                             [0, 3], [0, 7], [0, 15]],
        "capture_rate_hz": 20, "duration_s": 20,
        "reviewed_context_source": "diagnostic-context.json"}
    entries = []
    for suffix, other_first, response in CASE_VARIANTS:
        case_id = ROOT.name + "__" + suffix
        scene = {**base_scene, "case_id": case_id,
                 "other_entered_first": other_first, "ego_response_request": response}
        folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        opposite = suffix.startswith("opposite_")
        intent = suffix in ("opposite_intends_left", "opposite_makes_left")
        realized = suffix == "opposite_makes_left"
        if opposite:
            scene.update(other_highway="candidate-east-west", other_approach_road_id=20,
                         other_route_xy_m=[[15, 5.75], [5, 5.75], [2, 5.75],
                                           [-2, 5.75], [-5, 5.75], [-15, 5.75]])
        if realized:
            scene["other_route_xy_m"] = [[15, 5.75], [5, 5.75], [4, 5.75],
                                          [-0.066, 4.066], [-1.75, 0],
                                          [-1.75, -5], [-1.75, -15]]
        if suffix == "wide_same_crossing":
            scene["crossing"] = {**crossing,
                "crossing_id": "candidate-north-carriageway-crossing-diagnostic",
                "roadway_id": "candidate-east-west-westbound-carriageway",
                "bounds_xy_m": [-3.5, 3, 3.5, 7]}
            scene["ego_approach_road_id"] = 20
            scene["ego_route_xy_m"] = [[15, 5.75], [5, 5.75], [2, 5.75],
                                       [-2, 5.75], [-5, 5.75], [-15, 5.75]]
        scene.update(approach_relation="opposite" if opposite else "crossing",
                     left_turn_intent=intent, left_turn_realized=realized)
        packet = {
            "diagnostic_only": True,
            "source_note": "Worker-authored engineering OpenDRIVE; highway scope, devices, intent and Native waypoints are not source reviewed",
            "source_path": str(MAP_SOURCE.relative_to(ROOT.parent.parent)),
            "crossing": scene["crossing"],
            "law_context": {
                "map_source": scene["crossing"]["map_source_sha256"],
                "ego_highway": scene["ego_highway"], "other_highway": scene["other_highway"],
                "public_access_source": None, "device_inventory_source": None,
                "driver_scope_source": None, "public_access": False, "human_driver": False,
                "devices": [], "approach_relation": scene["approach_relation"],
                "left_turn_intent": intent, "left_turn_realized": realized}}
        write_json(folder / "diagnostic-context.json", packet)
        scene["reviewed_context_sha256"] = sha(folder / "diagnostic-context.json")
        write_json(folder / "scene.json", scene)
        write_json(folder / "config.json", config(scene))
        files = []
        for name in ("runner.py", "case_builder.py", "crossing_control.py",
                     "crossing_audit.py", "native_capture.py", "native_driver.py",
                     "analysis.py", "delivery_audit.py", "scene.json", "config.json",
                     "diagnostic-context.json", "candidate-map.xodr", "candidate-map-inventory.json",
                     "tests/test_diagnostic_bundle.py"):
            source = folder / name if name in ("scene.json", "config.json", "diagnostic-context.json") else ROOT / name
            files.append({"path": name, "content": source.read_text()})
        construction = {
            "law_id": "NRS-484B-250-1", "cell_id": "C125714",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "diagnostic_only": True, "entrypoint": "runner.py", "files": files,
            "recording_description": recording_description(),
            "mechanisms": ["source-hashed diagnostic route validation",
                           "source-bound original body audit", "explicit ego response request"],
            "measurement_plan": {"entry_and_clearance": "Original body frames; diagnostic scene has no legal validity"},
            "static_checks": ["exact runner/config binding", "Native diagnostic rejection",
                              "ego yield and advance request branches"],
            "termination_rules": ["diagnostic CPU check only; Native launch requires reviewed source replacement"]}
        write_json(folder / "construction.json", construction)
        entries.append({"case_id": case_id, "kind": "diagnostic",
                        "construction": str((folder / "construction.json").relative_to(ROOT)),
                        "construction_sha256": sha(folder / "construction.json"),
                        "candidate_risk": {"status": "physical", "reason": "Native waypoint loading and public-roadway context are unverified."},
                        "candidates": []})
    manifest = {
        "format": "worker-execution-manifest", "assignment_id": ROOT.name,
        "runtime_manifest_sha256": sha(ROOT.parent.parent / "runtime" / "SOURCE-MANIFEST.json"),
        "diagnostic_only": True,
        "cases": entries}
    write_json(ROOT / "diagnostic-execution-manifest.json", manifest)


if __name__ == "__main__":
    build()
