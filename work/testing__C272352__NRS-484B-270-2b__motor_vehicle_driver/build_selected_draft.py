"""Materialize nine source-gated primary bundles for pinned offline tests."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver"
SOURCES = ("runner.py", "passing_scene.py", "passing_controller.py",
           "passing_native_capture.py", "passing_probe.py", "analysis.py")
MEASUREMENT_KEYS = ("activation", "due_care_sources", "one_lane", "left_clearance",
                    "return_order", "special_authorization")
MEASUREMENT_METHODS = ("measure_activation", "measure_due_care_sources",
                       "measure_one_lane", "measure_left_clearance",
                       "measure_return_order", "measure_special_authorization")
CAMERAS = [{"name": name, "width": 1920 if i == 0 else 1280,
            "height": 1080 if i == 0 else 720, "fov_deg": 75,
            "pose_strategy": "reviewed one-lane road, qualifying rider, passing route"}
           for i, name in enumerate(("overview", "approach", "reference_corner",
                                     "driver_reference"))]
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second original pass",
                  "reference_frame": "source-sealed Native road axis and original frame",
                  "uncertainty": "actual motion and legal judgment require local review"}
                 for name, unit, method in (
                     ("body_envelopes", "m", "original ego and qualifying rider body extents"),
                     ("passing_clearance", "m", "minimum body gap during longitudinal overlap"),
                     ("return_order", "original frame", "first right return versus rider front"),
                     ("lane_controls", "source record", "one forward lane, centerline and zone"),
                     ("opposing_traffic", "source record", "original opposing trajectories"),
                     ("camera_identity", "frame", "four synchronized original camera streams"))],
    "context_inputs": [{"name": "reviewed_native_site_packet", "unit": "source record",
                        "method": "sealed map, lane, actors, controls, traffic and exception sources"}],
    "limitations": ["Synthetic fixtures prove CPU software only.",
                    "The 3-foot floor is statutory; safe distance, safely clear, due care and exceptions remain human judgments."]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("exact bundle exceeds 2 MiB")


def case_parameters(suffix):
    kind = ("electric_bicycle" if suffix.startswith("electric_bicycle") else
            "electric_scooter" if suffix.startswith("electric_scooter") else "bicycle")
    floor = .8 if suffix.endswith("below") else .9144 if suffix.endswith("at") else 1.2
    return {"control_kind": kind, "same_direction_lane_count_requested": 1,
            "target_clearance_m": floor,
            "return_request": "early" if suffix == "bike_return_early" else "after_clear",
            "route_request": ("centerline" if suffix == "centerline_authorized" else
                              "no_passing_zone" if suffix == "no_passing_zone_authorized" else
                              "within_right_half")}


def build():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    ids = [x["case_id"] for x in plan["cases"]]
    if len(ids) != 9 or len(set(ids)) != 9 or any(not x.startswith(AID + "__") for x in ids):
        raise ValueError("nine exact selected cases required")
    entries = []
    (HERE / "diagnostics").mkdir(exist_ok=True)
    for item in plan["cases"]:
        ident = item["case_id"]
        suffix = ident.removeprefix(AID + "__")
        case = {"case_id": ident, "target_law_id": "NRS-484B-270-2b",
                "cell_id": "C272352", "actor": "motor_vehicle_driver",
                **case_parameters(suffix), "recording_description": RECORDING}
        config = {"law_id": "NRS-484B-270-2b", "cell_id": "C272352",
                  "actor": "motor_vehicle_driver", "selected_case_id": ident,
                  "candidate_id": "primary", "rate_hz": 20, "duration_s": 45,
                  "physical_completion": {"criterion": "overtake_pass",
                      "motion_source": "trace.jsonl", "body_key": "vehicle_vertices_m",
                      "other_body_key": "bicycle_vertices_m", "lateral_transition_m": 0.5,
                      "minimum_progress_m": 1.0,
                      "completion_goal_method": "original body center crosses from behind to ahead of qualifying rider with lateral transition; engineering event only"},
                  "required_atoms": [], "source_packets": [], "cameras": CAMERAS,
                  "supported_case_ids": ids, "case": case}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8"),
                  "source": str((HERE / name).relative_to(ROOT))} for name in SOURCES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        files.append({"path": "tests/test_bundle.py",
                      "content": (HERE / "bundle_test.py").read_text(encoding="utf-8"),
                      "source": str((HERE / "bundle_test.py").relative_to(ROOT))})
        construction = {"law_id": "NRS-484B-270-2b", "cell_id": "C272352",
                        "actor": "motor_vehicle_driver", "case_id": ident,
                        "entrypoint": "runner.py", "recording_description": RECORDING,
                        "files": files}
        target = HERE / ("construction-selected-" + suffix + ".json")
        write(target, construction)
        if ident == ids[0]:
            write(HERE / "config.json", config)
            write(HERE / "construction.json", construction)
        rows = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if ident not in disposition["case_ids"]:
                continue
            rows.append({"disposition_index": index,
                         "requirement": disposition["requirement"],
                         "source": disposition["source"],
                         "output_key": MEASUREMENT_KEYS[index],
                         "method": MEASUREMENT_METHODS[index],
                         "value_type": "object", "kind": "measured",
                         "inputs": ["original-context.json", "original-trace.jsonl",
                                    "original-source-receipt.json", "video_frames.jsonl"]})
        contract_path = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract",
                              "case_id": ident, "requirements": rows,
                              "negative": {"remove": ["original-trace.jsonl"],
                                           "error_contains": "Missing required source: original-trace.jsonl"}})
        entries.append({"case_id": ident, "kind": "delivery", "construction": target.name,
                        "construction_sha256": sha(target),
                        "candidate_risk": item["candidate_risk"], "candidates": [],
                        "measurement_contract": str(contract_path.relative_to(HERE)),
                        "measurement_procedure": {"entrypoint": "analysis.py"}})
    write(HERE / "execution-manifest.selected-draft.json",
          {"format": "worker-execution-manifest", "assignment_id": AID,
           "status": "selected_primary_offline_proofs_pending",
           "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
           "cases": entries})
    return ids


if __name__ == "__main__":
    print("built selected primary bundles:", len(build()))
