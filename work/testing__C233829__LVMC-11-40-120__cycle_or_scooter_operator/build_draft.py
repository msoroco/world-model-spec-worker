"""Build seven exact source-gated rider bundles and diagnostic recipes."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from path_observation import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONOR = ROOT / "work/testing__C150116__NRS-484B-503__motor_vehicle_driver/diagnostics"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(",", ":") if compact else None,
                               indent=None if compact else 2) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("worker file exceeds 2 MiB: " + str(path))


def description():
    specs = (
        ("rider_facility", "source observation", "original rider body occupancy of path and roadway"),
        ("path_context", "source context", "reviewed adjacent path, roadway, condition and access"),
        ("device_classification", "source context", "original rider and covered device identity"),
        ("camera_frame_identity", "frame ID", "four synchronized original camera views"),
    )
    return {"channels": [{"name": name, "unit": unit, "method": method,
                          "sampling_rate_hz": 20, "time_window": "all 900 original frames",
                          "reference_frame": "original Native frame and reviewed path map",
                          "uncertainty": "fixture cannot establish physical provision, usability or legal compliance"}
                         for name, unit, method in specs],
            "context_inputs": [], "limitations": [
                "Path usability and access are independent source and legal reviews.",
                "Observed facility use does not itself establish compliance."]}


def site_for(case):
    case_id = case["case_id"]
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
            "map_id": "synthetic C233829 path protocol", "roadway_id": "road-a",
            "path_id": "path-a", "path_designation_source": "synthetic-designation",
            "path_adjacent_to_roadway": True, "sidewalk_status": "absent",
            "path_usability_status": case["path_usability_context"],
            "path_condition_source": "synthetic-condition-only",
            "access_restrictions_source": "synthetic-access-only",
            "ego_device_type": case["device_type"],
            "path_polygon": [[0, 0], [40, 0], [40, 2], [0, 2]],
            "roadway_polygon": [[0, 3], [40, 3], [40, 7], [0, 7]],
            "route_candidates": {"path": [[1, 1], [39, 1]],
                                 "roadway": [[1, 5], [39, 5]]}}


def rows_for(case):
    roadway = case["rider_facility"] == "roadway"
    return [{"frame_index": i, "native_frame": 100 + i,
             "time_s": i / 20, "ego_actor_id": "diagnostic-rider",
             "ego_device_type": case["device_type"],
             "ego_body_on_roadway": roadway,
             "ego_body_on_designated_path": not roadway,
             "body_corners_xy": [[1 + i * 0.04, 4.8 if roadway else .8],
                                 [1.2 + i * 0.04, 4.8 if roadway else .8],
                                 [1.2 + i * 0.04, 5 if roadway else 1],
                                 [1 + i * 0.04, 5 if roadway else 1]]}
            for i in range(900)]


def main():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    cases = plan["cases"]
    ids = [case["case_id"] for case in cases]
    if len(ids) != 7 or len(set(ids)) != 7:
        raise ValueError("seven exact rider cases required")
    branch = plan["selected_branches"][0]
    plan["selected_branch"] = branch["branch"]
    plan["requirement_dispositions"] = [{"requirement": branch["requirement"],
        "source": branch["source"], "status": "selected_required", "case_ids": ids,
        "evidence_or_gap": "No accepted original recording; path designation, condition, access and rider body require original source review.",
        "reason": "Three covered devices, route alternatives and reviewed usability context remain separately observable."}]
    plan["observations"] = [{"name": name, "mandatory": True} for name in
        ("rider_facility", "path_context", "device_classification", "camera_frame_identity")]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": view, "subject": subject,
                      "interval": "all original 900 frames"} for view, subject in zip(CAMERAS,
            ("path and roadway extent", "rider entry and device identity",
             "path boundary and condition", "rider body on path or roadway"))]}
    for case in cases:
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["construction_status"] = "source_gated_exact_bundle"
    for comparison in plan["comparisons"]:
        comparison["status"] = "selected_source_gated"
    plan["planning_status"] = "selected_seven_source_gated_cases_four_comparisons"
    write(plan_path, plan)
    donor_gen = json.loads((DONOR / "stop_no_passenger-generator.json").read_text())
    donor_folder = DONOR / "stop_no_passenger"
    desc = description()
    entries = []
    scripts = ("source_deferred_runner.py", "path_observation.py", "path_route.py",
               "source_site.py", "analysis.py")
    for case in cases:
        cid = case["case_id"]
        name = cid.removeprefix(ASSIGNMENT + "__")
        site = site_for(case)
        config = {"assignment_id": ASSIGNMENT, "law_id": "LVMC-11-40-120",
                  "cell_id": "C233829", "actor": "cycle_or_scooter_operator",
                  "selected_case_id": cid, "supported_case_ids": ids,
                  "rate_hz": 20, "duration_s": 45, "required_atoms": [],
                  "source_packets": [], "cameras": list(CAMERAS),
                  "case": {"case_id": cid, "device_type": case["device_type"],
                           "target_facility": case["rider_facility"],
                           "path_usability_context": case["path_usability_context"],
                           "recording_description": desc}}
        files = {script: (HERE / script).read_text() for script in scripts}
        files["runner.py"] = files["source_deferred_runner.py"]
        files["config.json"] = json.dumps(config, indent=2) + "\n"
        files["tests/test_bundle.py"] = (
            '"""Exact source-gated rider bundle preflight."""\n'
            'from runner import check\n\n'
            'def test_bundle():\n'
            '    case_id, device, target, condition = check()\n'
            '    assert case_id.endswith("__" + device + "__" + target + "__" + condition + "_path")\n')
        construction = {"law_id": "LVMC-11-40-120", "cell_id": "C233829",
                        "actor": "cycle_or_scooter_operator", "case_id": cid,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": desc,
                        "files": [{"path": path, "content": content} for path, content in files.items()],
                        "measurement_plan": "900 original rider body/camera joins and reviewed path context",
                        "static_checks": ["reviewed source hashes", "route inside named facility"],
                        "termination_rules": ["900 synchronized Native ticks", "restore world"],
                        "mechanisms": ["source-gated rider spawn", "four-camera Native capture"]}
        construction_path = HERE / ("construction-" + name + ".json")
        write(construction_path, construction)
        folder = HERE / "diagnostics" / name
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / "site.json", site)
        write(folder / "diagnostic-source-note.json", {
            "source_kind": "synthetic_diagnostic_fixture",
            "accepted_original_source": False, "case_id": cid})
        row_path = folder / "rider-history.jsonl"
        row_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows_for(case)))
        copied = []
        for relative in ("trace.jsonl", "video_frames.jsonl",
                         "capture/native/frames.jsonl", "capture/evidence.jsonl"):
            destination = folder / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(donor_folder / relative, destination)
            copied.append({"path": relative, "source": str(destination.relative_to(ROOT)),
                           "sha256": sha(destination)})
        for filename in ("site.json", "diagnostic-source-note.json", "rider-history.jsonl"):
            source = folder / filename
            copied.append({"path": filename, "source": str(source.relative_to(ROOT)),
                           "sha256": sha(source)})
        gen = json.loads(json.dumps(donor_gen))
        capture = json.loads(gen["files"]["capture/manifest.json"])
        capture["case_id"] = cid
        capture["sources"]["trace.jsonl"] = sha(folder / "trace.jsonl")
        gen["files"]["capture/manifest.json"] = json.dumps(capture, indent=2) + "\n"
        gen_path = HERE / "diagnostics" / (name + "-generator.json")
        write(gen_path, gen, compact=True)
        recipe_path = HERE / "diagnostics" / (name + "-recipe.json")
        write(recipe_path, {"format": "worker-fixture-recipe", "sources": copied,
                            "generator": {"source": str(gen_path.relative_to(ROOT)),
                                          "sha256": sha(gen_path)}})
        contract_path = HERE / "diagnostics" / (name + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract", "case_id": cid,
            "requirements": [{"disposition_index": 0, "requirement": branch["requirement"],
                "source": branch["source"], "output_key": "rider_facility_use",
                "method": "measure_rider_facility", "value_type": "object", "kind": "measured",
                "inputs": ["rider-history.jsonl", "site.json", "diagnostic-source-note.json"]}],
            "negative": {"remove": ["rider-history.jsonl"],
                         "error_contains": "Missing required source: rider-history.jsonl"}})
        entries.append({"case_id": cid, "kind": "delivery",
                        "construction": construction_path.name,
                        "construction_sha256": sha(construction_path),
                        "fixture_recipe": str(recipe_path.relative_to(ROOT)),
                        "measurement_contract": str(contract_path.relative_to(HERE)),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "source_gate": "reviewed original municipal path designation, condition, access, rider device and Native site required",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "none", "reason":
                            "No fallback route is justified before source map and path access survey; primary has explicit route/visibility failure checks."},
                        "candidates": []})
    write(HERE / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT, "status": "source_gated_draft",
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print("source-gated rider draft cases:", main())
