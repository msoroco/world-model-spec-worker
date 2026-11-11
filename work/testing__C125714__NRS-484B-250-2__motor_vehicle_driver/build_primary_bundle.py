"""Build a synthetic CPU-only primary construction and partial manifest.

The embedded site documents are explicitly synthetic. They demonstrate
materialization and lazy Native checks; they are not an actual reviewed site.
"""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
CASE = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__source_verified_other_right_near_time"
SOURCES = ("polygon_source", "entrance_source", "median_spacing_source",
           "device_review_source", "statutory_crossing_review_source",
           "approach_geometry_source")
CODE = ("runner.py", "native_pair.py", "yield_controller.py", "route_control.py",
        "camera_setup.py", "camera_encoder.py", "capture_sources.py",
        "site_packet.py", "median_spacing.py", "finalizer.py", "entry_measurements.py")


def content(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256((PACKAGE / path).read_bytes()).hexdigest()


def build():
    site = {"native_map_name": "SyntheticFixtureTown", "crossing_id": 7,
            "ego_highway_id": 1, "other_highway_id": 2,
            "crossing_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
            "selected_roadway_index": 0,
            "same_statutory_crossing_reviewed": True,
            "ego_approach": [-10,0,0,0], "ego_entry": [-4,0,0,0],
            "other_approach": [0,-10,0,90], "other_entry": [0,-4,0,90],
            "routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                       "other": [[0,-10],[0,-4],[0,0],[0,10]]},
            "cameras": {"overview": [0,0,25,0,-90,0],
                        "approach": [-15,0,8,0,-20,0],
                        "reference_corner": [10,10,10,225,-30,0],
                        "driver_reference": [0,0,1.4,0,0,0]},
            "diagnostic_site_only": True}
    documents = {
        "polygon_source": {"format": "synthetic-median-polygon", "polygon_xy_m": site["crossing_polygon_xy_m"],
                           "physical_site_verified": False},
        "entrance_source": {"format": "synthetic-entrance-plan", "entrances": [11,22],
                            "physical_site_verified": False},
        "median_spacing_source": {"format": "worker-median-roadway-geometry", "units": "m",
                                  "source_description": "synthetic CPU median roadway pair",
                                  "roadway_polygons_xy_m": [
                                      [[-5,-5],[5,-5],[5,5],[-5,5]],
                                      [[-5,6],[5,6],[5,16],[-5,16]]]},
        "device_review_source": {"format": "worker-median-device-inventory",
                                 "crossing_id": 7, "native_map_name": "SyntheticFixtureTown",
                                 "all_entrances_reviewed": True,
                                 "review_basis": "synthetic CPU entrance and empty-device fixture",
                                 "entrances": [{"road_id": 11,"lane_id": -1,"highway_id": 1},
                                               {"road_id": 22,"lane_id": -1,"highway_id": 2}],
                                 "devices": []},
        "statutory_crossing_review_source": {"format": "synthetic-statutory-review",
                                               "legal_conclusion": "unresolved"},
        "approach_geometry_source": {"format": "synthetic-approach-geometry",
                                     "native_motion_verified": False}}
    files = []
    source_refs = {}
    for key in SOURCES:
        path = "site-sources/" + key + ".json"
        value = content(documents[key])
        files.append({"path": path, "content": value})
        site[key] = path
        source_refs[key] = {"path": path, "sha256": sha(value)}
    packet_path = "site-review.json"
    packet = content({"format": "worker-median-site-review",
                      "review_status": "reviewed_candidate",
                      "diagnostic_only": True, "site": site,
                      "source_documents": source_refs})
    files.append({"path": packet_path, "content": packet})
    config = {"selected_case_id": CASE, "supported_case_ids": [CASE],
              "law_id": "NRS-484B-250-2", "cell_id": "C125714",
              "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 55,
              "cameras": [{"name": name, "width": size[0], "height": size[1],
                            "pose_strategy": "synthetic CPU geometry; Native coverage unverified",
                            "fov_deg": 90}
                           for name, size in (("overview", (1920,1080)),
                                              ("approach", (1280,720)),
                                              ("reference_corner", (1280,720)),
                                              ("driver_reference", (1280,720)))],
              "required_atoms": ["ru.subject", "ru.motor_vehicle", "kin.position",
                                 "kin.velocity", "kin.speed", "st.intersection", "rel.bearing"],
              "source_packets": [], "case": {"diagnostic_only": True},
              "recording_description": {"channels": [{"name": "yield_control", "unit": "structured record",
                  "method": "Original controller frame joined to body history", "time_window": "entire capture",
                  "reference_frame": "original Native frame", "uncertainty": "synthetic fixture only",
                  "sampling_rate_hz": 20}],
                  "context_inputs": [{"name": "entry_context", "unit": "structured record",
                      "method": "Saved body entry and sourced crossing geometry"}],
                  "limitations": ["Diagnostic media and site have no physical or legal acceptance"]},
              "physical_completion": {"criterion": "intersection_clearance",
                                      "motion_source": "crossing_history.jsonl",
                                      "body_key": "ego_vertices_m",
                                      "context_sources": ["road_geometry.json"],
                                      "exit_axis": 0, "exit_sign": 1},
              "ego_target_speed_mps": 5, "other_target_speed_mps": 5,
              "other_release_frame": 20,
              "site_review": {"path": packet_path, "sha256": sha(packet)},
              "site": site}
    files.append({"path": "config.json", "content": content(config)})
    for name in CODE:
        files.append({"path": name, "content": (PACKAGE / name).read_text()})
    files.append({"path": "tests/test_bundle.py", "content":
                  "import json, unittest\nfrom runner import validate_config\n"
                  "class BundleTest(unittest.TestCase):\n"
                  " def test_reviewed_synthetic_bundle(self):\n"
                  "  config=json.load(open('config.json'))\n"
                  "  self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])\n"})
    proposal = {"case_id": CASE, "law_id": "NRS-484B-250-2", "cell_id": "C125714",
                "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                "recording_description": config["recording_description"],
                "files": files, "status": "synthetic_diagnostic_only",
                "measurement_plan": {"source": "crossing_history.jsonl",
                                     "saved_finalizer": "finalizer.py"}}
    construction = content(proposal)
    (PACKAGE / "construction.json").write_text(construction)
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": PACKAGE.name,
                "runtime_manifest_sha256": hashlib.sha256((ROOT / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                "cases": [{"case_id": CASE, "kind": "delivery",
                           "construction": "construction.json",
                           "construction_sha256": sha(construction),
                           "measurement_procedure": {"entrypoint": "finalizer.py"},
                           "measurement_contract": "measurement-contract.json",
                           "fixture_recipe": "work/" + PACKAGE.name + "/diagnostic-recipe.json",
                           "offline": {"exit_code": 0,
                                       "construction_sha256": sha(construction),
                                       "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + PACKAGE.name + "/execution-manifest.json --case " + CASE + " --output .runtime-work/c125714-250-2-primary-offline-v8",
                                       "log": "primary-offline.log",
                                       "log_sha256": file_sha("primary-offline.log")},
                           "compatibility": {"receipt": "primary-compatibility-receipt.json",
                                             "sha256": file_sha("primary-compatibility-receipt.json"),
                                             "log": "primary-compatibility-analysis.log"},
                           "negative": {"log": "primary-negative-analysis.log"},
                           "acquisition": {
                               "ru.subject": {"entrypoint": "capture_sources.py", "method": "source actor identity", "evidence": "capture/evidence.jsonl"},
                               "ru.motor_vehicle": {"entrypoint": "capture_sources.py", "method": "Native vehicle blueprint", "evidence": "capture/evidence.jsonl"},
                               "kin.position": {"entrypoint": "capture_sources.py", "method": "original body and pose", "evidence": "trace.jsonl"},
                               "kin.velocity": {"entrypoint": "capture_sources.py", "method": "original actor velocity", "evidence": "trace.jsonl"},
                               "kin.speed": {"entrypoint": "capture_sources.py", "method": "original actor velocity magnitude", "evidence": "trace.jsonl"},
                               "st.intersection": {"entrypoint": "site_packet.py", "method": "source-bound crossing polygon and Native junction", "evidence": "road_geometry.json"},
                               "rel.bearing": {"entrypoint": "entry_measurements.py", "method": "sourced approach projection", "evidence": "road_geometry.json"},
                               "yield_control": {"entrypoint": "finalizer.py", "method": "original controller-frame join", "evidence": "controller_history.jsonl"}},
                           "candidate_risk": {"status": "physical",
                                              "reason": "Native approach timing or camera coverage may fail"},
                           "candidates": []}]}
    (PACKAGE / "execution-manifest.json").write_text(content(manifest))
    return manifest


if __name__ == "__main__":
    print(content(build()))
