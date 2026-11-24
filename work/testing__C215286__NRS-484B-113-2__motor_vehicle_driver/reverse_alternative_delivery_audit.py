"""Independent CPU delivery boundary for intersection and corner reverse cases."""

import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT_ROOT = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not OUTPUT_ROOT or not Path(OUTPUT_ROOT).resolve().is_relative_to(REPO / ".runtime-work"):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.measurement_contract import verify_report  # noqa: E402
from worker_exchange.media import audit as audit_video  # noqa: E402
from reverse_alternatives import analyze  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id):
    attempt = Path(attempt).resolve()
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    if entry is None or entry["measurement_procedure"]["entrypoint"] != "reverse_alternative_finalizer.py":
        raise ValueError("Unselected alternative reverse case")
    construction = HERE / entry["construction"]
    if sha(construction) != entry["construction_sha256"]:
        raise ValueError("Selected alternative construction changed")
    suffix = case_id.split("__")[-1]
    alternative = "street_corner" if "street_corner" in suffix else "intersection"
    expected = suffix in ("reverse_into_intersection", "reverse_around_street_corner")
    source = analyze(attempt, alternative)
    if source["reverse_body_enters_region"] is not expected:
        raise ValueError("Original reverse region outcome differs from selected case")
    report = json.loads((attempt / "analysis-report.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if report.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Saved case identity differs")
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
        raise ValueError("This CPU audit requires explicit synthetic provenance")
    contract = json.loads((HERE / entry["measurement_contract"]).read_text())
    measured = verify_report(contract, report, attempt)
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line]
    if len(mapping) != len(trace) or len(mapping) != 900:
        raise ValueError("Full 900-frame original trace and camera map required")
    if any(row["carla_frame"] != motion["frame"] or abs(row["time_s"] - motion["time_s"]) > 1e-6
           for row, motion in zip(mapping, trace)):
        raise ValueError("Original camera and motion frame join differs")
    if any(result.get("physical_checks", {}).get(key, {}).get("status") != "met"
           for key in ("setup", "target", "maneuver", "attempt")):
        raise ValueError("Synthetic physical checker did not complete")
    decodes = {}
    for camera in ("overview", "approach", "reference_corner", "driver_reference"):
        video = attempt / (camera + ".mkv")
        decodes[camera] = audit_video(video, 900, mapping_sha256=sha(attempt / "video_frames.jsonl"))
    return {"format": "worker-c215286-alternative-delivery-cpu-boundary", "case_id": case_id,
            "construction_sha256": sha(construction), "source_hashes": source["source_sha256"],
            "report_sha256": sha(attempt / "analysis-report.json"),
            "result_sha256": sha(attempt / "result.json"), "measurement_keys": sorted(measured),
            "frames": 900, "camera_decodes": decodes, "software_audit_passed": True,
            "native_source_accepted": False, "actual_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: reverse_alternative_delivery_audit.py ATTEMPT CASE_ID")
    print(json.dumps(audit(sys.argv[1], sys.argv[2]), indent=2))
