"""Bind the two selected crossing requests to exact executable candidates."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = HERE / "native" / "crossing"
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
TERMS = ("ru.subject", "ru.pedestrian", "st.intersection", "st.lane_enters",
         "dev.traffic_signal", "st.crosswalk", "rel.occupies", "st.roadway",
         "kin.position")
CASES = ("marked_crosswalk", "unmarked_midblock")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


OFFLINE_TEST = '''import json
from pathlib import Path
import unittest
from runner import check_config
from original_saved import required

class ExactCrossingOffline(unittest.TestCase):
    def test_selected_capture_profile(self):
        config = json.loads(Path("config.json").read_text())
        result = check_config(config)
        self.assertEqual(result["frames"], 600)
        self.assertEqual(result["camera_count"], 4)
        self.assertFalse(result["native_executed"])

    def test_missing_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing required source: controls-original.jsonl"):
            required(Path.cwd(), "controls-original.jsonl")
'''


def description():
    return {"channels": [{"name": name, "unit": "structured" if name.startswith(("ru.", "st.", "dev.", "rel.")) else "m",
                           "sampling_rate_hz": 20,
                           "method": "joined original Native frame, survey and pedestrian footprint",
                           "time_window": "all 600 original frames",
                           "reference_frame": "original Native frame and elapsed time",
                           "uncertainty": "50 ms sampled intervals; actual pixels and legal exception pending independent review",
                           "source": "channels/" + name + ".jsonl"} for name in TERMS],
            "context_inputs": [{"name": "nrs_484b_290_exception", "unit": "source",
                                "method": "retain unavailable exact statute and person-specific applicability as unknown"}],
            "limitations": ["Actual local map adjacency, official device applicability and NRS 484B.290 require independent review"]}


def construction(case, candidate, desc):
    case_id = ASSIGNMENT + "__" + case
    height = 5.0 if candidate == "primary" else 3.0
    config = {"assignment_id": ASSIGNMENT, "case_id": case_id,
              "selected_case_id": case_id, "candidate_id": candidate,
              "requested_crossing_location": case, "cell_id": "C109166",
              "law_id": "NRS-484B-287-1c", "actor": "pedestrian",
              "frames": 600, "rate_hz": 20, "duration_s": 30,
              "camera_dimensions": {name: [width, height] for name, width, height in CAMERAS},
              "detail_camera_height_m": height,
              "cameras": [{"name": name, "width": width, "height": height_px,
                           "fov_deg": 90, "pose_strategy": "source-bound fixed Native view"}
                          for name, width, height_px in CAMERAS],
              "required_atoms": ["ru.pedestrian", "st.intersection", "st.lane_enters",
                                 "dev.traffic_signal", "st.crosswalk", "rel.occupies",
                                 "st.roadway", "kin.position"],
              "source_packets": [],
              "physical_completion": {"criterion": "travel_progress",
                                      "motion_source": "pedestrian-original.jsonl",
                                      "position_key": "center_xy_m",
                                      "direction_xy": [0, 1],
                                      "minimum_progress_m": 12,
                                      "minimum_samples": 2,
                                      "completion_goal_method": "body center crosses the authored road width plus approach; engineering progress, not law"},
              "recording_description": desc}
    inline = {"runner.py": (SOURCE / "original_capture.py").read_text(),
              "scene.py": (SOURCE / "scene.py").read_text(),
              "original_capture.py": (SOURCE / "original_capture.py").read_text(),
              "original_saved.py": (SOURCE / "original_saved.py").read_text(),
              "finalize.py": (SOURCE / "finalize_original.py").read_text()}
    files = [{"path": name, "content": content} for name, content in inline.items()]
    files += [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
              {"path": "tests/test_offline.py", "content": OFFLINE_TEST}]
    return {"case_id": case_id, "cell_id": "C109166", "law_id": "NRS-484B-287-1c",
            "actor": "pedestrian", "entrypoint": "runner.py", "files": files,
            "recording_description": desc,
            "measurement_plan": {"method": "original pedestrian footprint, pair of controls and surveyed marked crossing at entry",
                                 "status": "selected_cpu_draft"},
            "static_checks": ["two independently surveyed junctions and distinct control actors",
                              "600 original frame/trace joins", "four original RGB cameras"],
            "termination_rules": ["30-second original capture", "retain failed status and restoration report"],
            "mechanisms": ["CARLA pedestrian controller", "source-gated map and control readback",
                           "PipelineCapture original trace and FrameMap", "saved-only original source audit"],
            "status": "selected_cpu_draft"}


def build():
    desc = description()
    cases = []
    for case in CASES:
        case_id = ASSIGNMENT + "__" + case
        paths = {}
        for candidate in ("primary", "fallback1"):
            obj = construction(case, candidate, desc)
            path = HERE / "cases" / case / candidate / "construction.json"
            write(path, obj)
            paths[candidate] = path
            if case == CASES[0] and candidate == "primary":
                write(HERE / "construction.json", obj)
                for item in obj["files"]:
                    target = HERE / item["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(item["content"])
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [
                {"disposition_index": 0, "requirement": "text-0", "source": "inputs/coverage/branch-sources.json",
                 "output_key": "between_intersections_crossing", "method": "between_intersections_crossing_measurement",
                 "value_type": "object", "kind": "measured",
                 "inputs": ["pedestrian-original.jsonl", "controls-original.jsonl",
                            "native-survey.json", "video_frames.jsonl"]},
                {"disposition_index": 1, "requirement": "text-1", "source": "inputs/coverage/branch-sources.json",
                 "output_key": "nrs_484b_290_exception", "method": "exception_applicability_measurement",
                 "value_type": "object", "kind": "sourced_context",
                 "inputs": ["exception-applicability-source.json"]},
                {"disposition_index": 2, "requirement": "reviewed-scope-0", "source": "inputs/coverage/branch-sources.json",
                 "output_key": "crossing_scope", "method": "scope_crossing_measurement",
                 "value_type": "object", "kind": "measured",
                 "inputs": ["pedestrian-original.jsonl", "controls-original.jsonl",
                            "native-survey.json", "video_frames.jsonl"]}],
            "negative": {"remove": ["controls-original.jsonl"],
                         "error_contains": "Missing required source: controls-original.jsonl"}}
        contract_path = HERE / "cases" / case / "measurement-contract.json"
        write(contract_path, contract)
        cases.append({"case_id": case_id, "kind": "delivery",
            "construction": str(paths["primary"].relative_to(HERE)),
            "construction_sha256": sha(paths["primary"]),
            "measurement_contract": str(contract_path.relative_to(HERE)),
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "worker-analysis-report-v1"},
            "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic-{case}-recipe.json",
            "candidate_risk": {"status": "physical",
                "reason": "The marked-crosswalk and control views may be too high to resolve original pixels"},
            "candidates": [{"id": "fallback1",
                "construction": str(paths["fallback1"].relative_to(HERE)),
                "construction_sha256": sha(paths["fallback1"]),
                "trigger": {"source": "original reference_corner camera pixels",
                            "metric": "marking visible height in pixels",
                            "failure_condition": "marked crossing stripe below 12 pixels in primary"},
                "changed_knobs": ["detail_camera_height_m: 5.0 to 3.0"]}]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(ROOT / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "selected_cpu_draft", "delivery_ready": False,
                "original_native_observed": False, "cases": cases}
    write(HERE / "execution-manifest.json", manifest)
    proposal = {"cell_id": "C109166", "actor": "pedestrian", "status": "draft",
                "sweep_specs": [], "sweeps_expanded": [], "cases": []}
    for case in CASES:
        proposal["cases"].append({"case_id": ASSIGNMENT + "__" + case,
            "target_law_id": "NRS-484B-287-1c", "target_type": "attempt",
            "rationale": "Source-bound crossing-location contrast under the same two operating controls",
            "variable_assignments": {"crossing_location": {"kind": "world_setup", "value": case},
                                     "exception_484b_290": {"kind": "sourced_context",
                                                              "value": "independent review pending"}},
            "unresolved_judgment_calls": ["adjacent intersections", "official devices in operation",
                                           "NRS 484B.290 person-specific exception"],
            "recording_description": desc})
    write(HERE / "proposals" / "cases.json", proposal)
    return {"cases": len(cases), "candidates": 4, "manifest_sha256": sha(HERE / "execution-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build()))
