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
from worker_exchange.native_output import provenance_record  # noqa: E402
from worker_exchange.saved_processing import _closure  # noqa: E402
from worker_exchange.candidate_constructions import select  # noqa: E402
from worker_exchange.common import digest  # noqa: E402
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


def audit_native(attempt, case_id, owner_receipt):
    """Inspect a sealed original Native capture and its saved report; leave pixel review open."""
    attempt = Path(attempt).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    if entry is None or entry["measurement_procedure"]["entrypoint"] != "reverse_alternative_finalizer.py":
        raise ValueError("Unselected Native alternative reverse case")
    provenance = provenance_record(attempt)
    if provenance["provenance_kind"] != "native" or provenance["diagnostic_fixture"] is not False:
        raise ValueError("Original non-diagnostic Native provenance required")
    seal_path = attempt / "capture-seal.json"
    seal = json.loads(seal_path.read_text())
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native"
            or seal.get("diagnostic_fixture") is not False or seal.get("frames") != 900
            or seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]
            or seal.get("source_digest") != digest(seal.get("sources", {}))):
        raise ValueError("Native capture seal or duration differs")
    _closure(attempt, owner_receipt, "native", False)
    selection_path = attempt / "candidate-selection.json"
    selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {"candidate_id": "primary"}
    candidate_id = selection.get("candidate_id")
    _, selected, _ = select(manifest_path, case_id, candidate_id)
    if sha(attempt / "construction.json") != selected["construction_sha256"]:
        raise ValueError("Native construction differs from selected candidate")
    if selection_path.is_file() and (selection.get("case_id") != case_id
            or selection.get("construction_sha256") != selected["construction_sha256"]
            or selection.get("manifest_sha256") != sha(manifest_path)):
        raise ValueError("Native candidate selection differs from current manifest")
    config = json.loads((attempt / "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("Native config selects another case")
    suffix = case_id.split("__")[-1]
    alternative = "street_corner" if "street_corner" in suffix else "intersection"
    expected = suffix in ("reverse_into_intersection", "reverse_around_street_corner")
    site_name = alternative + ("_site.json" if expected else "_stop_site.json")
    site = json.loads((attempt / site_name).read_text())
    if (site.get("site_review_status") != "reviewed_native_site" or not site.get("site_reviewer")
            or not site.get("site_review_basis") or not site.get("camera_review_basis")):
        raise ValueError("Original Native site and camera review required")
    source = analyze(attempt, alternative)
    if source["reverse_body_enters_region"] is not expected or len(source["samples"]) != 900:
        raise ValueError("Original Native reverse region outcome differs")
    needed = {"construction.json", "runner.py", "config.json", "reverse_history.jsonl",
              "video_frames.jsonl", "trace.jsonl", "reverse_site_context.json", site_name,
              "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"}
    needed.update(source["source_sha256"])
    if not needed <= set(seal["sources"]):
        raise ValueError("Native seal omits original route, site or camera source")
    for name in needed:
        if sha(attempt / name) != seal["sources"][name]:
            raise ValueError("Sealed Native original source changed: " + name)
    report = json.loads((attempt / "analysis-report.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if report.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Native saved report case identity differs")
    if (result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is not False
            or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native saved report provenance or acceptance claim differs")
    if any(result.get("physical_checks", {}).get(key, {}).get("status") != "met"
           for key in ("setup", "target", "maneuver", "attempt")):
        raise ValueError("Native saved physical completion is incomplete")
    contract = json.loads((HERE / entry["measurement_contract"]).read_text())
    measured = verify_report(contract, report, attempt)
    decodes = {camera: audit_video(attempt / (camera + ".mkv"), 900,
                                   mapping_sha256=sha(attempt / "video_frames.jsonl"))
               for camera in ("overview", "approach", "reference_corner", "driver_reference")}
    return {"format": "worker-c215286-alternative-native-source-preflight", "case_id": case_id,
            "candidate_id": candidate_id, "capture_seal_sha256": sha(seal_path),
            "owner_release_sha256": sha(owner_receipt), "source_hashes": source["source_sha256"],
            "measurement_keys": sorted(measured), "camera_decodes": decodes,
            "native_source_preflight_passed": True, "actual_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    if len(sys.argv) == 3:
        print(json.dumps(audit(sys.argv[1], sys.argv[2]), indent=2))
    elif len(sys.argv) == 5 and sys.argv[1] == "--native":
        print(json.dumps(audit_native(sys.argv[2], sys.argv[3], sys.argv[4]), indent=2))
    else:
        raise SystemExit("usage: reverse_alternative_delivery_audit.py [--native] ATTEMPT CASE_ID [OWNER_RECEIPT]")
