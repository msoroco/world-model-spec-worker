"""Build one exact unselected 30-minute Native request for pinned offline check."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.parent.name
CASE = ASSIGNMENT + "__probe_b"
OUT = ROOT.parent / "draft-native"


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def build():
    road = (ROOT / "parking-road.xodr").read_text()
    runner = (ROOT / "draft_runner.py").read_text()
    cameras = [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 85, "location_xyz_m": [-8, -4, 18], "pitch_deg": -55},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 90, "location_xyz_m": [3, 0, 2], "pitch_deg": -5},
        {"name": "curb", "width": 1280, "height": 720, "fov_deg": 75, "location_xyz_m": [0, -4, 3], "pitch_deg": -25},
        {"name": "device", "width": 1280, "height": 720, "fov_deg": 90, "location_xyz_m": [0, 0, 2], "pitch_deg": -10},
    ]
    config = {
        "format": "c229398-night-parking-native-request-v1",
        "status": "unselected_native_request",
        "assignment_id": ASSIGNMENT,
        "case_id": CASE,
        "selected_case_id": CASE,
        "law_id": "LVMC-11-52-300",
        "cell_id": "C229398",
        "actor": "nonmotor_vehicle_operator",
        "prototype_blueprint": "vehicle.bh.crossbike",
        "device_classification": "unresolved",
        "road_sha256": sha(road),
        "rate_hz": 20,
        "capture_frames": 36043,
        "duration_s": 36043 / 20,
        "approach_frames": 40,
        "cameras": cameras,
        "required_atoms": [],
        "source_packets": [],
        "case": {"case_id": CASE},
        "original_native_observed": False,
        "physical_or_legal_acceptance": False,
    }
    tests = "\n".join([
        "import json",
        "import sys",
        "import unittest",
        "from pathlib import Path",
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
        "from runner import check, request",
        "",
        "class TestExactRequest(unittest.TestCase):",
        "    def test_source_and_duration(self):",
        "        result = check()",
        "        cfg = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())",
        "        self.assertEqual(result['frames'], 36043)",
        "        self.assertEqual(request(40, cfg)['phase'], 'stationary_request')",
        "        self.assertEqual(request(36042, cfg)['phase'], 'stationary_request')",
        "        self.assertFalse(result['physical_or_legal_acceptance'])",
        "",
    ])
    bundle = {
        "case_id": CASE,
        "law_id": "LVMC-11-52-300",
        "cell_id": "C229398",
        "actor": "nonmotor_vehicle_operator",
        "entrypoint": "runner.py",
        "status": "unselected_native_request",
        "files": [
            {"path": "runner.py", "content": runner},
            {"path": "parking-road.xodr", "content": road},
            {"path": "config.json", "content": encoded(config)},
            {"path": "tests/test_request.py", "content": tests},
        ],
        "recording_description": {
            "duration_s": 36043 / 20,
            "rate_hz": 20,
            "camera_views": [v["name"] for v in cameras],
            "limitations": ["Crossbike blueprint does not certify nonmotor vehicle class",
                            "No Native execution or real source media captured"],
        },
    }
    OUT.mkdir(exist_ok=True)
    construction = OUT / "construction.json"
    construction.write_text(encoded(bundle))
    manifest = {
        "format": "worker-unselected-draft-construction-manifest-v1",
        "assignment_id": ASSIGNMENT,
        "status": "draft_not_selected",
        "cases": [{
            "case_id": CASE,
            "kind": "draft_not_selected",
            "construction": "draft-native/construction.json",
            "construction_sha256": sha(construction.read_text()),
            "candidates": [],
        }],
    }
    manifest_path = ROOT.parent / "draft-native-manifest.json"
    manifest_path.write_text(encoded(manifest))
    print(encoded({"construction": str(construction), "construction_sha256": sha(construction.read_text()),
                   "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path.read_text())}), end="")


if __name__ == "__main__":
    build()
