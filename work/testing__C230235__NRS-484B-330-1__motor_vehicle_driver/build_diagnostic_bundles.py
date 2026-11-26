"""Build exact offline bundles that refuse unsourced original Native capture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from flagger_zone import CASES, SOURCES
from source_packet import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

RUNNER = '''"""Exact flagger-zone diagnostic entrypoint; no original source is selected."""
import argparse
import json
from pathlib import Path
from source_packet import verify


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    checked = verify(root / "source-packet.json", diagnostic_fixture=True)
    if checked["case_id"] != config["selected_case_id"]:
        raise ValueError("diagnostic case identity differs")
    if config["rate_hz"] != 20 or config["duration_s"] != 45:
        raise ValueError("capture profile differs")
    print("exact diagnostic source packet verified; original capture refused")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    args = parser.parse_args()
    if not args.check:
        raise ValueError("diagnostic fixture cannot run original Native capture")
    check()
'''

TEST = '''import json
from pathlib import Path
import unittest
import runner
from source_packet import verify


class ExactBundleTest(unittest.TestCase):
    def test_offline_case_and_synthetic_provenance(self):
        runner.check()
        with self.assertRaisesRegex(ValueError, "provenance"):
            verify(Path(__file__).resolve().parents[1] / "source-packet.json")


if __name__ == "__main__":
    unittest.main()
'''


def digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    expected = {entry["case_id"] for entry in plan["cases"]}
    if expected != {ASSIGNMENT + "__" + case.name for case in CASES}:
        raise ValueError("planned cases differ from controller cases")
    entries = []
    for case in CASES:
        cid = ASSIGNMENT + "__" + case.name
        scene = {"cell_id": "C230235", "actor": "motor_vehicle_driver",
                 "qualifying_vehicle": True, "highway": True,
                 "driver_id": "diagnostic-driver", "vehicle_id": "diagnostic-vehicle",
                 "flagger_id": "diagnostic-flagger", "designated": case.designated,
                 "marked_construction": case.marked_construction,
                 "authorized": case.authorized, "signal": case.signal,
                 "response": case.response, "zone_rect_m": [0, 0, 50, 10],
                 "stop_line_xy": [10, 5], "flagger_xy": [10, 8],
                 "vehicle_route_xy": [[0, 5], [50, 5]],
                 "signal_frame": 100, "release_frame": 200}
        files = []
        refs = {}
        for name in (*SOURCES, "map_opendrive"):
            content = "SYNTHETIC SOFTWARE FIXTURE: " + name + "\n"
            path = name + ".txt"
            checksum = digest(content)
            files.append({"path": path, "content": content})
            refs[name] = {"path": path, "sha256": checksum,
                          "observation": "Synthetic software fixture for " + name,
                          "review_status": "synthetic"}
            scene["map_opendrive_sha256" if name == "map_opendrive"
                  else name + "_source_sha256"] = checksum
        packet = {"assignment_id": ASSIGNMENT, "case_id": cid,
                  "source_kind": "synthetic_fixture", "review_status": "synthetic",
                  "scene": scene, "source_refs": refs}
        config = {"law_id": "NRS-484B-330-1", "cell_id": "C230235",
                  "actor": "motor_vehicle_driver", "selected_case_id": cid,
                  "rate_hz": 20, "duration_s": 45, "capture_frames": 900,
                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "source_packets": ["source-packet.json"],
                  "source_kind": "synthetic_fixture", "diagnostic_only": True}
        files.extend([{"path": "source-packet.json", "content": json.dumps(packet, indent=2, sort_keys=True) + "\n"},
                      {"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
                      {"path": "runner.py", "content": RUNNER},
                      {"path": "tests/test_case.py", "content": TEST}])
        for name in ("flagger_zone.py", "source_packet.py", "capture_seal.py",
                     "native_acquisition.py", "process_saved.py", "delivery_audit.py",
                     "comparison_audit.py"):
            files.append({"path": name, "content": (HERE / name).read_text()})
        description = {"channels": [
            {"name": name, "method": method, "unit": "structured",
             "time_window": "all 900 original world ticks",
             "reference_frame": "reviewed C230235 CARLA world frame",
             "sampling_rate_hz": 20,
             "uncertainty": "original realization and visibility await Native review"}
            for name, method in (
                ("original_vehicle_motion", "Original vehicle position, body and speed sealed to world ticks"),
                ("flagger_signal", "Original signal, orientation, visibility, recipient and release sealed to world ticks"),
                ("camera_pixels", "Four synchronized original camera images"))],
            "context_inputs": [{"name": name, "unit": "structured",
                                "method": "Independently reviewed original source finding for " + name}
                               for name in ("flagger_authorization", "traffic_control_role",
                                            "zone_designation", "construction_marking",
                                            "signal_content", "vehicle_motion")],
            "limitations": ["Synthetic fixture is not a reviewed zone or actual Native motion."]}
        construction = {"law_id": "NRS-484B-330-1", "cell_id": "C230235",
                        "actor": "motor_vehicle_driver", "case_id": cid,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": description, "files": files}
        construction_path = HERE / ("construction-diagnostic-" + case.name + ".json")
        write(construction_path, construction)
        entries.append({"case_id": cid, "kind": "capability_research",
                        "construction": construction_path.name,
                        "construction_sha256": sha(construction_path)})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "status": "diagnostic_only_original_source_pending",
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    write(HERE / "execution-manifest.diagnostic.json", manifest)
    return {"cases": len(entries), "manifest_sha256": sha(HERE / "execution-manifest.diagnostic.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
