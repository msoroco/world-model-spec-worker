"""Build four exact inline engineering bundles and a partial manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bus_route import ROUTES
from native_construction import check_scene


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
FILES = ("runner.py", "native_construction.py", "bus_route.py", "source_review.py",
         "lane_signal_measurement.py", "analysis.py", "native_driver.py",
         "native_capture.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def recording_description():
    channels = (
        ("bus_full_body_footprint", "Original bus bounding-box XY corners on every world tick"),
        ("governed_lane_bounds", "Original imported map lane identity and lateral bounds"),
        ("overhead_red_x_state", "Original facing overhead signal symbol and lane association"),
        ("camera_frame_map", "Original four-camera synchronized frame identities"),
    )
    return {"channels": [{"name": name, "unit": "structured source record",
                          "method": method, "sampling_rate_hz": 20,
                          "time_window": "every original captured frame",
                          "reference_frame": "original CARLA world and frame/time",
                          "uncertainty": "Native import, device pixels and full-body motion require later review"}
                         for name, method in channels],
            "context_inputs": [{"name": "reviewed_highway_and_official_device",
                                "unit": "retained original source packet",
                                "method": "source_review.validate before Native dispatch"}],
            "limitations": ["Engineering map and sign placement do not establish public highway or official device status.",
                            "Requested route does not establish actual entry or driving."]}


def build():
    cases = []
    previous_path = ROOT / "execution-manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    previous_entries = {entry["case_id"]: entry for entry in previous.get("cases", [])}
    all_ids = [ASSIGNMENT + "__" + kind for kind in ROUTES]
    for kind in ROUTES:
        folder = ROOT / "cases" / kind
        scene = json.loads((folder / "scene.json").read_text())
        scene["map_source"] = "road.xodr"
        check_scene(scene, ROOT / "candidate-red-x-road.xodr")
        config = {"assignment_id": ASSIGNMENT, "selected_case_id": scene["case_id"],
                  "supported_case_ids": all_ids, "law_id": scene["law_id"],
                  "cell_id": scene["cell_id"], "actor": scene["actor"],
                  "rate_hz": 20, "duration_s": 18, "required_atoms": [],
                  "source_packets": [], "case": kind,
                  "cameras": [{"name": name, "width": 1280, "height": 720,
                               "fov_deg": 90, "pose_strategy": ("bus mounted" if name == "driver_reference"
                                                               else "fixed close road view")}
                              for name in scene["capture_plan"]["cameras"]]}
        files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
                  "content": (ROOT / name).read_text()} for name in FILES]
        files.extend(({"path": "scene.json", "content": json.dumps(scene, indent=2) + "\n"},
                      {"path": "road.xodr", "source": str((ROOT / "candidate-red-x-road.xodr").relative_to(REPO)),
                       "content": (ROOT / "candidate-red-x-road.xodr").read_text()},
                      {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_offline.py", "source": str((ROOT / "offline_test.py").relative_to(REPO)),
                       "content": (ROOT / "offline_test.py").read_text()}))
        construction = {"law_id": scene["law_id"], "cell_id": scene["cell_id"],
                        "actor": scene["actor"], "case_id": scene["case_id"],
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": recording_description(),
                        "measurement_plan": {"red_x_bus_lane": "Source-joined full-body red-X entry and driving frames"},
                        "static_checks": ["two right-side same-direction 3.6 m driving lanes",
                                          "bus body target contained within roadway",
                                          "head target over governed lane"],
                        "source_kind": "worker engineering candidate; public highway and official device unverified"}
        path = folder / "construction.json"
        write(path, construction)
        entry = {"case_id": scene["case_id"], "kind": "delivery",
                      "construction": str(path.relative_to(ROOT)), "construction_sha256": sha(path),
                      "candidate_risk": {"status": "physical",
                                         "reason": "Live bus footprint, lane import and overhead sign visibility may differ from authored geometry"},
                      "preparation_status": "partial_offline_pending"}
        prior = previous_entries.get(scene["case_id"], {})
        if prior.get("construction_sha256") == entry["construction_sha256"]:
            for key in ("offline", "candidates", "compatibility", "post_capture", "delivery_acceptance"):
                if key in prior:
                    entry[key] = prior[key]
            entry["preparation_status"] = prior.get("preparation_status", entry["preparation_status"])
        cases.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "cases": cases, "preparation_status": "partial_offline_pending"}
    write(ROOT / "execution-manifest.json", manifest)
    return cases


if __name__ == "__main__":
    for entry in build():
        print(entry["case_id"], entry["construction_sha256"])
