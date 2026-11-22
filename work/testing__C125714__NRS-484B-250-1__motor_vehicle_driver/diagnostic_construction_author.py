"""Build an exact-ID CPU diagnostic bundle; never assert reviewed legal context."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_builder import config, recording_description
from map_inventory import inventory


ROOT = Path(__file__).resolve().parent
CASE_ID = ROOT.name + "__precedence"
MAP_SOURCE = ROOT.parent / "testing__C126120__NRS-484B-227-1__motor_vehicle_driver" / "candidate-intersection-candidate.xodr"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    # This map is another worker's engineering candidate. Its junction has no
    # declared connections, so these polylines have NOT passed Native binding.
    crossing = {"crossing_id": "candidate-central-crossing-diagnostic",
                "bounds_xy_m": [-3.5, -6.0, 3.5, 6.0],
                "map_source_sha256": sha(MAP_SOURCE)}
    (ROOT / "candidate-map.xodr").write_bytes(MAP_SOURCE.read_bytes())
    write_json(ROOT / "candidate-map-inventory.json", inventory(ROOT / "candidate-map.xodr"))
    packet = {
        "diagnostic_only": True,
        "source_note": "Worker-authored C126120 engineering OpenDRIVE candidate; no public-highway, device, or Native connectivity review",
        "source_path": str(MAP_SOURCE.relative_to(ROOT.parent.parent)),
        "crossing": crossing,
        "law_context": {
            "map_source": crossing["map_source_sha256"],
            "ego_highway": "candidate-east-west", "other_highway": "candidate-north-south",
            "public_access_source": None, "device_inventory_source": None,
            "driver_scope_source": None, "public_access": False, "human_driver": False,
            "devices": [], "approach_relation": "crossing",
            "left_turn_intent": False, "left_turn_realized": False}}
    write_json(ROOT / "diagnostic-context.json", packet)
    scene = {
        "diagnostic_only": True, "case_id": CASE_ID,
        "crossing": crossing, "ego_highway": "candidate-east-west",
        "other_highway": "candidate-north-south", "ego_approach_road_id": 10,
        "other_approach_road_id": 31,
        "ego_route_xy_m": [[-15, -5.75], [-2, -5.75], [0, -5.75], [15, -5.75]],
        "other_route_xy_m": [[0, -15], [0, -2], [0, 2], [0, 15]],
        "capture_rate_hz": 20, "duration_s": 20,
        "other_entered_first": True,
        "reviewed_context_source": "diagnostic-context.json",
        "reviewed_context_sha256": sha(ROOT / "diagnostic-context.json")}
    write_json(ROOT / "scene.json", scene)
    write_json(ROOT / "config.json", config(scene))
    files = []
    for name in ("runner.py", "case_builder.py", "crossing_control.py",
                 "crossing_audit.py", "native_capture.py", "native_driver.py",
                 "analysis.py", "delivery_audit.py", "scene.json", "config.json",
                 "diagnostic-context.json", "candidate-map.xodr", "candidate-map-inventory.json",
                 "tests/test_diagnostic_bundle.py"):
        files.append({"path": name, "content": (ROOT / name).read_text()})
    construction = {
        "law_id": "NRS-484B-250-1", "cell_id": "C125714",
        "actor": "motor_vehicle_driver", "case_id": CASE_ID,
        "diagnostic_only": True, "entrypoint": "runner.py", "files": files,
        "recording_description": recording_description(),
        "mechanisms": ["source-hashed diagnostic route validation", "source-bound original body audit"],
        "measurement_plan": {"entry_and_clearance": "Original body frames; diagnostic scene has no legal validity"},
        "static_checks": ["exact runner/config binding", "Native legal-context rejection"],
        "termination_rules": ["diagnostic CPU check only; Native launch requires reviewed source replacement"]}
    write_json(ROOT / "construction.json", construction)
    manifest = {
        "format": "worker-execution-manifest", "assignment_id": ROOT.name,
        "runtime_manifest_sha256": sha(ROOT.parent.parent / "runtime" / "SOURCE-MANIFEST.json"),
        "diagnostic_only": True,
        "cases": [{"case_id": CASE_ID, "kind": "diagnostic",
                   "construction": "construction.json", "construction_sha256": sha(ROOT / "construction.json"),
                   "candidate_risk": {"status": "physical", "reason": "Candidate OpenDRIVE junction connectivity and public-roadway context are unverified."},
                   "candidates": []}]}
    write_json(ROOT / "diagnostic-execution-manifest.json", manifest)


if __name__ == "__main__":
    build()
