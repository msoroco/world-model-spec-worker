"""Build eight exact unselected Native construction bundles for this assignment."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NATIVE = HERE / "native"
ASSIGNMENT = HERE.name
FILES = ("runner.py", "geometry.py", "controller.py", "engineering.py",
         "cameras.py", "measure.py", "finalize.py", "finalize-measure.py", "road.xodr")
TESTS = ("test_native.py",)
CHANNELS = ("drv.standing_or_parked", "st.intersection", "rel.occupies",
            "drv.forced_halt", "dev.human_direction", "dev.traffic_signal",
            "kin.velocity", "native_body_pose_control", "camera_frame_join")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    import sys
    sys.path.insert(0, str(NATIVE))
    from engineering import CANDIDATES, TRIGGERS, parameters
    batch = json.loads((REPO / "batch.json").read_text())
    shared = [{"path": name, "content": (NATIVE / name).read_text()} for name in FILES]
    shared += [{"path": "tests/" + name, "content": (NATIVE / name).read_text()}
               for name in TESTS]
    description = {"channels": [{"name": name, "unit": "structured",
                                "sampling_rate_hz": 20,
                                "method": "original Native body, map and controller sample",
                                "time_window": "24 s / 480 joined frames",
                                "reference_frame": "Native map and original frame",
                                "uncertainty": "50 ms sample; physical map and pixels pending"}
                               for name in CHANNELS],
                   "context_inputs": [{"name": "surveyed_intersection", "unit": "structured",
                                       "method": "Native OpenDRIVE readback and lane survey"}],
                   "limitations": ["Synthetic CPU proof is not observed CARLA behavior or legal verdict"]}
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "status": "draft_not_selected", "cases": []}
    proposals = []
    for suffix in ("probe_a", "probe_b"):
        case_id = ASSIGNMENT + "__" + suffix
        entry = {"case_id": case_id, "kind": "draft_not_selected",
                 "candidate_risk": {"status": "physical",
                                    "reason": "Native route/parking, original pixels and exceptions require original observations"},
                 "measurement_procedure": {"entrypoint": "finalize.py",
                                            "output_schema": "c110454-450-1c-saved-measurement-v1"},
                 "measurement_contract": f"draft-candidates/{suffix}/measurement-contract.json",
                 "candidates": []}
        write(HERE / entry["measurement_contract"], {
            "format": "worker-measurement-contract-v1", "case_id": case_id,
            "requirements": [{"disposition_index": 0, "requirement": "NRS-484B-450-1c",
                              "source": "inputs/training__C110454__NRS-484B-450-1c__motor_vehicle_driver/assignment.json",
                              "output_key": "intersection_parking_footprint",
                              "method": "measure_saved_footprint", "value_type": "object",
                              "kind": "measured", "inputs": ["native_samples.jsonl"]}],
            "negative": {"remove": ["native_samples.jsonl"],
                         "error_contains": "Missing required source: native_samples.jsonl"}})
        proposals.append({"case_id": case_id, "target_law_id": "NRS-484B-450-1c",
                          "target_type": "attempt", "recording_description": description})
        for candidate in CANDIDATES:
            plan = parameters(suffix, candidate)
            config = {"case_id": case_id, "selected_case_id": case_id,
                      "supported_case_ids": [case_id], "case": {"case_id": case_id},
                      "case_suffix": suffix, "candidate_id": candidate,
                      "cell_id": "C110454", "law_id": "NRS-484B-450-1c",
                      "actor": "motor_vehicle_driver", "duration_s": 24, "rate_hz": 20,
                      "required_atoms": ["st.intersection", "rel.occupies", "kin.velocity"],
                      "source_packets": [], "mandatory_channels": list(CHANNELS),
                      "recording_description": description,
                      "cameras": [{"name": name, "width": width, "height": height}
                                  for name, width, height in
                                  (("overview", 1920, 1080), ("approach", 1280, 720),
                                   ("intersection", 1280, 720), ("parking", 1280, 720))],
                      "engineering_knobs": plan["knobs"],
                      "status": "unselected_native_runner_prototype"}
            files = shared + [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
            construction = {"case_id": case_id, "cell_id": "C110454",
                            "law_id": "NRS-484B-450-1c", "actor": "motor_vehicle_driver",
                            "entrypoint": "runner.py", "files": files,
                            "recording_description": description,
                            "measurement_plan": {"method": "saved original full body overlap and sustained stop",
                                                 "status": "unselected_cpu_proposal"},
                            "static_checks": ["authored intersection and full-body endpoint",
                                              "source-bound 480-frame synthetic measurement",
                                              "fallback trigger positive and negative"],
                            "termination_rules": ["480 original joined frames", "restore world"],
                            "mechanisms": ["two-way intersection", "observed-pose stop controller",
                                           "four synchronized lossless cameras"],
                            "status": "unselected_cpu_draft"}
            path = HERE / "draft-candidates" / suffix / candidate / "construction.json"
            write(path, construction)
            ref = {"id": candidate, "construction": str(path.relative_to(HERE)),
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update(ref)
            else:
                trigger = TRIGGERS[candidate]
                ref["trigger"] = trigger | {"failure_condition":
                    f"{trigger['metric']} {trigger['op']} {trigger['threshold']}"}
                ref["changed_knobs"] = list(plan["knobs"].keys() - parameters(suffix, "primary")["knobs"].keys()) or \
                    [key for key, value in plan["knobs"].items()
                     if value != parameters(suffix, "primary")["knobs"][key]]
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    write(HERE / "draft-execution-manifest.json", manifest)
    write(HERE / "proposals" / "cases.json", {"cell_id": "C110454",
          "actor": "motor_vehicle_driver", "status": "draft", "cases": proposals})
    print(json.dumps({"cases": len(manifest["cases"]), "candidates": 8,
                      "status": "unselected"}))


if __name__ == "__main__": main()
