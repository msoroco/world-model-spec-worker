"""Build current-hash selected yield bundles without inventing reviewed sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
COMMON = ("runner.py", "native_capture.py", "native_output_bridge.py",
          "yield_scene_construction.py", "yield_view_measurement.py",
          "through_motion_measurement.py", "saved_finalizer.py", "analysis.py",
          "delivery_audit.py", "physical_completion.py", "case-plan.json")
TESTS = tuple(sorted("tests/" + p.name for p in (ROOT / "tests").glob("test*.py")
                     if p.name != "test_source_and_queue.py"))
CHANNELS = ("yield_sign_and_marking", "nearest_view_stations", "ego_motion_and_crossing",
            "through_vehicle_motion", "governing_control", "original_four_camera_pixels")
ACQUISITION = {
    "yield_sign_and_marking": ("native_capture.py", "reviewed-site.json and reviewed-sources.json", "SHA-verified reviewed yield sign and marking survey"),
    "nearest_view_stations": ("yield_view_measurement.py", "original-trace.jsonl and reviewed-view_ray_survey_sha256.source", "Original approach samples projected against reviewed view rays"),
    "ego_motion_and_crossing": ("native_capture.py", "original-trace.jsonl", "20 Hz original ego body and crossing readback"),
    "through_vehicle_motion": ("native_capture.py", "original-trace.jsonl", "20 Hz original through-vehicle body readback"),
    "governing_control": ("native_capture.py", "context.json and original-trace.jsonl", "Reviewed control joined to original frame observations"),
    "original_four_camera_pixels": ("native_capture.py", "cameras.json and four source MKV streams", "Synchronized original RGB readback and source video hashes"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    original = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    prior_path = ROOT / "execution-manifest.json"
    prior = {entry["case_id"]: entry for entry in json.loads(prior_path.read_text()).get("cases", [])} if prior_path.exists() else {}
    ids = [case["case_id"] for case in plan["cases"]]
    record = {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                            "time_window": "all 900 original frames", "reference_frame": "reviewed original yield intersection",
                            "method": "source-sealed original Native readback",
                            "uncertainty": "reviewed site and physical yield outcome pending"}
                           for name in CHANNELS],
              "context_inputs": [{"name": "reviewed_yield_site_source", "unit": "source",
                                  "method": "independent SHA-256 reviewed source packet"}],
              "limitations": ["Immediate hazard has no invented numeric legal cutoff.",
                              "Stop-sign catalog annotation does not establish a governed yield site."]}
    cameras = [{"name": name, "width": width, "height": height, "fov_deg": 80,
                "pose_strategy": "reviewed yield sign, nearest view and through highway sightline"}
               for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))]
    base = {"assignment_id": ASSIGNMENT, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "duration_s": 45, "rate_hz": 20, "cameras": cameras,
            "supported_case_ids": ids, "required_atoms": [], "source_packets": [],
            "plan_sha256": sha((ROOT / "case-plan.json").read_bytes())}
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()),
                "status": "partial_source_pending", "cases": []}
    for ordinal, case in enumerate(plan["cases"]):
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        config = {**base, "selected_case_id": case_id,
                  "case": {"case_id": case_id, "recording_description": record}}
        if ordinal == 0:
            write(ROOT / "config.json", config)
        folder = ROOT / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / "config-materialized.json", config)
        files = [{"path": name, "content": (ROOT / name).read_text()} for name in COMMON]
        files.append({"path": "config.json", "content": (ROOT / "config.json").read_text()
                      if ordinal == 0 else (folder / "config-materialized.json").read_text()})
        files.extend({"path": name, "content": (ROOT / name).read_text()} for name in TESTS)
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                        "actor": plan["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "files": files,
                        "measurement_plan": {"case_id": case_id, "procedure": "analysis.py",
                                             "source_packets": ["reviewed_original_yield_site", "original_context",
                                                                "original_trace", "original_camera_manifest"],
                                             "legal_judgment": "unresolved"},
                        "recording_description": record,
                        "mechanisms": ["reviewed yield-control variant", "no stop line/crosswalk survey",
                                       "nearest-view ray survey", "source-sealed Native through traffic",
                                       "four synchronized RGB cameras"],
                        "static_checks": ["exact assignment/plan hash", "independent reviewed source bytes",
                                          "900-frame 20 Hz four-view protocol"],
                        "termination_rules": ["stop on source or Native readback mismatch",
                                              "restore Native settings and destroy owned actors"],
                        "status": "source_gated_incomplete"}
        target = ROOT / "construction.json" if ordinal == 0 else folder / "construction.json"
        write(target, construction)
        digest = sha(target.read_bytes())
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": "NRS 484B.257(1)", "kind": "measured",
                                      "method": "measure", "output_key": "nearest_view_yield_event",
                                      "value_type": "object",
                                      "inputs": ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json"]}],
                    "negative": {"remove": ["context.json"],
                                 "error_contains": "Missing required source: context.json"}}
        write(folder / "measurement-contract.json", contract)
        entry = {**prior.get(case_id, {}), "case_id": case_id, "kind": "delivery",
                                  "status": "source_pending", "construction": str(target.relative_to(ROOT)),
                                  "construction_sha256": digest,
                                  "measurement_contract": str((folder / "measurement-contract.json").relative_to(ROOT)),
                                  "measurement_procedure": {"entrypoint": "analysis.py",
                                                            "method": "source-bound original nearest-view and through-motion measurement"},
                                  "missing_proofs": ["reviewed_yield_site", "original_native_capture",
                                                     "positive_negative_compatibility", "saved_only_original",
                                                     "physical_preparation", "delivery_acceptance"]}
        entry["acquisition"] = {name: {"entrypoint": source, "evidence": evidence, "method": method}
                                for name, (source, evidence, method) in ACQUISITION.items()}
        if "delivery_acceptance" in entry:
            entry["delivery_acceptance"]["sets"] = original["selection_targets"]
        manifest["cases"].append(entry)
    write(ROOT / "execution-manifest.json", manifest)
    print(len(manifest["cases"]), "source-pending selected bundles")


if __name__ == "__main__":
    main()
