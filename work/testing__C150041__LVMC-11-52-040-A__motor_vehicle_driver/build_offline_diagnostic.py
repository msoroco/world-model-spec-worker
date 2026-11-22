"""Build one explicit synthetic, offline-only C150041 construction bundle.

This fixture never establishes a real roadway, Chapter applicability, Native
motion or delivery readiness. The live wrapper rejects this diagnostic packet.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_pose import REQUESTS
from parking_scene import ASSIGNMENT, build


ROOT = Path(__file__).resolve().parent
KINDS = tuple(REQUESTS)
MODULES = ("parking_measurement.py", "parking_pose.py", "source_review.py",
           "parking_scene.py", "parking_control.py", "parking_native_driver.py",
           "parking_native_capture.py", "parking_cameras.py", "parking_tick_capture.py",
           "parking_finalizer.py", "parking_comparison_audit.py",
           "parking_delivery_audit.py", "parking_analysis.py", "parking_runner.py")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build_bundle(kind="park_parallel_lawful"):
    if kind not in KINDS:
        raise ValueError("unknown exact diagnostic case")
    directory = ROOT / "diagnostic" / kind
    sources_dir = directory / "reviewed_sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name in ("roadway", "one_way_direction", "activity", "chapter_exceptions"):
        path = sources_dir / (name + ".txt")
        path.write_text("Synthetic C150041 offline protocol source: " + name + "\n")
        sources[name] = {"path": path.relative_to(directory).as_posix(),
                         "sha256": _sha(path), "reviewer": "synthetic fixture author",
                         "citation": "offline protocol fixture only"}
    packet = {"assignment_id": ASSIGNMENT, "review_status": "reviewed",
              "sources": sources,
              "context": {"roadway_kind": "one_way_road",
                          "responsible_person_role": "motor_vehicle_driver",
                          "activity": REQUESTS[kind][0], "chapter_exception_review": "unresolved",
                          "road_edge_xy_m": [[-20, 0], [20, 0]],
                          "roadway_polygon_xy_m": [[-20, 0], [20, 0], [20, 5], [-20, 5]],
                          "lawful_travel_xy": [1, 0]}}
    packet_path = directory / "reviewed-context.json"
    _write(packet_path, packet)
    scene = build(packet_path, directory, kind)
    fallback_scene = build(packet_path, directory, kind, approach_distance_m=6.0)
    semantic_cases = json.loads((ROOT / "proposals" / "cases.json").read_text())["cases"]
    semantic_case = next(item for item in semantic_cases if item["case_id"] == scene["case_id"])
    config = {"assignment_id": ASSIGNMENT, "selected_case_id": scene["case_id"],
              "law_id": "LVMC-11-52-040-A", "cell_id": "C150041",
              "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 12,
              "required_atoms": [], "source_packets": [],
              "case": {"case_id": scene["case_id"],
                       "recording_description": semantic_case["recording_description"]},
              "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                           "height": 1080 if name == "overview" else 720,
                           "fov_deg": 90, "pose_strategy": "source-bound fixed or vehicle attached"}
                          for name in scene["capture_plan"]["cameras"]]}
    wrapper = '''"""Synthetic offline-only C150041 bundle wrapper."""
import sys
from parking_runner import main
if __name__ == "__main__":
    if "--check" not in sys.argv:
        raise ValueError("synthetic diagnostic bundle cannot launch Native capture")
    sys.argv.extend(["--packet", "reviewed-context.json", "--source-root", ".",
                     "--case", "CASE_KIND"])
    main()
'''.replace("CASE_KIND", kind)
    test = '''"""Exact synthetic bundle construction smoke test."""
import json
import unittest
from pathlib import Path
from parking_scene import build

class OfflineParkingBundle(unittest.TestCase):
    def test_exact_source_bound_scene(self):
        scene = build("reviewed-context.json", ".", "CASE_KIND")
        config = json.loads(Path("config.json").read_text())
        self.assertEqual(scene["case_id"], config["selected_case_id"])
        self.assertEqual(len(config["cameras"]), 4)
        self.assertFalse(scene["physical_realization_claimed"])

if __name__ == "__main__": unittest.main()
'''.replace("CASE_KIND", kind)
    files = [{"path": name, "content": (ROOT / name).read_text()} for name in MODULES]
    files += [{"path": "runner.py", "content": wrapper},
              {"path": "tests/test_offline.py", "content": test},
              {"path": "scene.json", "content": json.dumps(scene, indent=2) + "\n"},
              {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
              {"path": "reviewed-context.json", "content": packet_path.read_text()}]
    files += [{"path": descriptor["path"], "content": (directory / descriptor["path"]).read_text()}
              for descriptor in sources.values()]
    construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                    "actor": config["actor"], "case_id": scene["case_id"],
                    "entrypoint": "runner.py", "files": files,
                    "recording_description": config["case"]["recording_description"],
                    "measurement_plan": {"parking_orientation_heading":
                                         "Original source-joined body and lawful-edge geometry"},
                    "static_checks": ["source packet hashes", "full body within roadway",
                                      "exact activity and four-camera plan"],
                    "source_kind": "synthetic_offline_protocol_fixture_only"}
    construction_path = directory / "construction.json"
    _write(construction_path, construction)
    fallback = json.loads(json.dumps(construction))
    for item in fallback["files"]:
        if item["path"] == "runner.py":
            item["content"] = item["content"].replace('"--case", "' + kind + '"]',
                '"--case", "' + kind + '", "--approach-distance-m", "6.0"]')
        elif item["path"] == "tests/test_offline.py":
            item["content"] = item["content"].replace('"' + kind + '")',
                '"' + kind + '", approach_distance_m=6.0)')
        elif item["path"] == "scene.json":
            item["content"] = json.dumps(fallback_scene, indent=2) + "\n"
    fallback_path = directory / "construction-fallback1.json"
    _write(fallback_path, fallback)
    manifest_path = directory / "diagnostic-manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous_cases = previous.get("cases", [])
    previous_candidates = previous_cases[0].get("candidates", []) if previous_cases else []
    candidate = {"id": "fallback1", "construction": "construction-fallback1.json",
                 "construction_sha256": _sha(fallback_path),
                 "trigger": {"source": "reviewed roadway geometry and full vehicle footprint",
                             "metric": "primary spawn footprint inside roadway",
                             "failure_condition": "8 m approach footprint outside reviewed roadway; 6 m footprint inside"},
                 "changed_knobs": ["approach_distance_m: 8.0 to 6.0"]}
    if previous_candidates:
        prior = previous_candidates[0]
        proof = prior.get("offline", {})
        proof_log = directory / proof.get("log", "")
        if (prior.get("construction_sha256") == candidate["construction_sha256"]
                and proof.get("construction_sha256") == candidate["construction_sha256"]
                and proof_log.is_file() and _sha(proof_log) == proof.get("log_sha256")):
            candidate["offline"] = proof
    _write(manifest_path, {"assignment_id": ASSIGNMENT, "diagnostic_only": True,
                           "cases": [{"case_id": scene["case_id"], "kind": "diagnostic_only",
                                      "construction": "construction.json",
                                      "construction_sha256": _sha(construction_path),
                                      "measurement_procedure": {"entrypoint": "parking_analysis.py"},
                                      "candidate_risk": {"status": "physical", "reason":
                                          "An 8 m straight approach may not fit a reviewed roadway segment while a shorter approach does."},
                                      "candidates": [candidate],
                                      "preparation_status": "synthetic_offline_only"}]})
    return manifest_path, scene["case_id"]


if __name__ == "__main__":
    for kind in KINDS:
        path, case_id = build_bundle(kind)
        print(path, case_id)
