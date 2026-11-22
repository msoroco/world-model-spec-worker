"""Build one explicit synthetic, offline-only C150041 construction bundle.

This fixture never establishes a real roadway, Chapter applicability, Native
motion or delivery readiness. The live wrapper rejects this diagnostic packet.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_scene import ASSIGNMENT, build


ROOT = Path(__file__).resolve().parent
KIND = "park_parallel_lawful"
MODULES = ("parking_measurement.py", "parking_pose.py", "source_review.py",
           "parking_scene.py", "parking_control.py", "parking_native_driver.py",
           "parking_native_capture.py", "parking_cameras.py", "parking_tick_capture.py",
           "parking_finalizer.py", "parking_comparison_audit.py",
           "parking_delivery_audit.py", "parking_runner.py")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build_bundle():
    directory = ROOT / "diagnostic" / KIND
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
                          "activity": "park", "chapter_exception_review": "unresolved",
                          "road_edge_xy_m": [[-20, 0], [20, 0]],
                          "roadway_polygon_xy_m": [[-20, 0], [20, 0], [20, 5], [-20, 5]],
                          "lawful_travel_xy": [1, 0]}}
    packet_path = directory / "reviewed-context.json"
    _write(packet_path, packet)
    scene = build(packet_path, directory, KIND)
    config = {"assignment_id": ASSIGNMENT, "selected_case_id": scene["case_id"],
              "law_id": "LVMC-11-52-040-A", "cell_id": "C150041",
              "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 12,
              "required_atoms": [], "source_packets": [],
              "case": {"case_id": scene["case_id"],
                       "recording_description": json.loads((ROOT / "proposals" / "cases.json").read_text())["cases"][1]["recording_description"]},
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
                     "--case", "park_parallel_lawful"])
    main()
'''
    test = '''"""Exact synthetic bundle construction smoke test."""
import json
import unittest
from pathlib import Path
from parking_scene import build

class OfflineParkingBundle(unittest.TestCase):
    def test_exact_source_bound_scene(self):
        scene = build("reviewed-context.json", ".", "park_parallel_lawful")
        config = json.loads(Path("config.json").read_text())
        self.assertEqual(scene["case_id"], config["selected_case_id"])
        self.assertEqual(len(config["cameras"]), 4)
        self.assertFalse(scene["physical_realization_claimed"])

if __name__ == "__main__": unittest.main()
'''
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
    manifest_path = directory / "diagnostic-manifest.json"
    _write(manifest_path, {"assignment_id": ASSIGNMENT, "diagnostic_only": True,
                           "cases": [{"case_id": scene["case_id"], "kind": "diagnostic_only",
                                      "construction": "construction.json",
                                      "construction_sha256": _sha(construction_path),
                                      "preparation_status": "synthetic_offline_only"}]})
    return manifest_path, scene["case_id"]


if __name__ == "__main__":
    path, case_id = build_bundle()
    print(path, case_id)
