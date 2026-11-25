"""Source-bound CPU preflight for a sealed Native reverse-crosswalk capture.

This does not review actual pixels or make a legal determination.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or not Path(output_root).resolve().is_relative_to(REPO / ".runtime-work"):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))

from worker_exchange.candidate_constructions import select  # noqa: E402
from worker_exchange.common import digest  # noqa: E402
from worker_exchange.media import audit as audit_video  # noqa: E402
from worker_exchange.measurement_contract import verify_report  # noqa: E402
from worker_exchange.native_output import provenance_record  # noqa: E402
from worker_exchange.saved_processing import _closure  # noqa: E402
from crosswalk_reverse import analyze  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def _joined_20hz(attempt):
    names = ("video_frames.jsonl", "trace.jsonl", "reverse_history.jsonl")
    rows = [[json.loads(line) for line in (attempt / name).read_text().splitlines() if line]
            for name in names]
    if any(len(part) != 900 for part in rows):
        raise ValueError("Original 900-frame camera and reverse history required")
    for index, (frame, trace, motion) in enumerate(zip(*rows)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != trace.get("frame")
                or frame.get("carla_frame") != motion.get("frame")
                or frame.get("time_s") != trace.get("time_s")
                or frame.get("time_s") != motion.get("time_s")
                or not motion.get("native_reverse") or not motion.get("ego_body_vertices_xy_m")):
            raise ValueError("Original camera, trace or reverse-body join differs")
        if index and (frame["carla_frame"] <= rows[0][index - 1]["carla_frame"]
                      or abs(frame["time_s"] - rows[0][index - 1]["time_s"] - .05) > .001):
            raise ValueError("Original 20 Hz camera ordering differs")


def audit(attempt, case_id, owner_receipt):
    attempt = Path(attempt).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    if entry is None or not case_id.endswith(("reverse_over_crosswalk", "reverse_stops_before_crosswalk")):
        raise ValueError("Unselected Native crosswalk case")
    provenance = provenance_record(attempt)
    if provenance["provenance_kind"] != "native" or provenance["diagnostic_fixture"] is not False:
        raise ValueError("Original non-diagnostic Native provenance required")
    seal_path = attempt / "capture-seal.json"
    seal = read(seal_path)
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native"
            or seal.get("diagnostic_fixture") is not False or seal.get("frames") != 900
            or seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]
            or seal.get("source_digest") != digest(seal.get("sources", {}))):
        raise ValueError("Native capture seal or duration differs")
    _closure(attempt, owner_receipt, "native", False)
    selection_path = attempt / "candidate-selection.json"
    selection = read(selection_path) if selection_path.is_file() else {"candidate_id": "primary"}
    candidate_id = selection.get("candidate_id")
    _, selected, _ = select(manifest_path, case_id, candidate_id)
    if sha(attempt / "construction.json") != selected["construction_sha256"]:
        raise ValueError("Native construction differs from selected candidate")
    if selection_path.is_file() and (selection.get("case_id") != case_id
            or selection.get("construction_sha256") != selected["construction_sha256"]
            or selection.get("manifest_sha256") != sha(manifest_path)):
        raise ValueError("Native candidate selection differs from current manifest")
    config = read(attempt / "config.json")
    if config.get("selected_case_id") != case_id:
        raise ValueError("Native config selects another case")
    site = read(attempt / "site_packet.json")
    if (site.get("site_review_status") != "reviewed_native_site" or not site.get("reviewer")
            or not site.get("district_review_basis") or not site.get("crosswalk_review_basis")
            or not site.get("camera_review_basis")
            or any("synthetic" in str(site.get(key, "")).lower() for key in
                   ("reviewer", "district_review_basis", "crosswalk_review_basis", "camera_review_basis"))):
        raise ValueError("Original Native district and crosswalk review required")
    _joined_20hz(attempt)
    source = analyze(attempt)
    expected = case_id.endswith("reverse_over_crosswalk")
    if (source["reverse_body_on_or_over_crosswalk"] is not expected
            or not source["backward_motion_observed"] or len(source["samples"]) != 900):
        raise ValueError("Original Native reverse crosswalk outcome differs")
    needed = {"construction.json", "runner.py", "config.json", "trace.jsonl",
              "reverse_history.jsonl", "video_frames.jsonl", "site_packet.json",
              "crosswalk_context.json", "overview.mkv", "approach.mkv",
              "reference_corner.mkv", "driver_reference.mkv"}
    needed.update(source["sources"])
    if not needed <= set(seal["sources"]):
        raise ValueError("Native seal omits original reverse, site or camera source")
    for name in needed:
        if sha(attempt / name) != seal["sources"][name]:
            raise ValueError("Sealed Native original source changed: " + name)
    result, report = read(attempt / "result.json"), read(attempt / "analysis-report.json")
    if result.get("case_id") != case_id or report.get("case_id") != case_id:
        raise ValueError("Native saved report case identity differs")
    if (result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is not False
            or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native saved report provenance or acceptance claim differs")
    if any(result.get("physical_checks", {}).get(key, {}).get("status") != "met"
           for key in ("setup", "target", "maneuver", "attempt")):
        raise ValueError("Native saved physical completion is incomplete")
    measured = verify_report(read(HERE / entry["measurement_contract"]), report, attempt)
    mapping_sha = sha(attempt / "video_frames.jsonl")
    decodes = {name: audit_video(attempt / (name + ".mkv"), 900, mapping_sha256=mapping_sha)
               for name in ("overview", "approach", "reference_corner", "driver_reference")}
    return {"format": "worker-c215286-crosswalk-native-source-preflight", "case_id": case_id,
            "candidate_id": candidate_id, "capture_seal_sha256": sha(seal_path),
            "owner_release_sha256": sha(owner_receipt), "source_hashes": source["sources"],
            "measurement_keys": sorted(measured), "camera_decodes": decodes,
            "native_source_preflight_passed": True, "actual_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt")
    parser.add_argument("case_id")
    parser.add_argument("owner_receipt")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case_id, args.owner_receipt), indent=2))
