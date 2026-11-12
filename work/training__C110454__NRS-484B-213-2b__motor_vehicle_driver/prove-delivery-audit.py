"""Exercise C110454 delivery audit without accepting synthetic footage."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import (CAMERAS, TARGET, ZONE_KIND, audit, check_context_review,
                            check_pixel_review, selected_entry)
from source_join_audit import sha


def require(value, message):
    if not value:
        raise ValueError(message)


def reject(name, operation, rejected):
    try:
        operation()
    except ValueError:
        rejected.append(name)
    else:
        raise AssertionError("Delivery audit mutation accepted: " + name)


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    index = json.loads((HERE / "update019-selected-six-index.json").read_text())
    require(len(index["results"]) == 24 and index["manifest_sha256"] ==
            sha(HERE / "execution-manifest.json"), "Selected proof index differs")
    checked = []
    for row in index["results"]:
        suffix = row["case_id"].removeprefix(HERE.name + "__")
        entry = next(item for item in manifest["cases"] if item["case_id"] == row["case_id"])
        candidate = entry if row["candidate_id"] == "primary" else next(
            item for item in entry["candidates"] if item["id"] == row["candidate_id"])
        path = ROOT / ".runtime-work/c110454-update019-six-selected" / suffix / row["candidate_id"]
        result = audit(path / "compatibility", path / "saved/v0001/processing.json",
                       row["case_id"], row["candidate_id"], candidate["construction_sha256"],
                       diagnostic=True)
        require(result["passed"] is False and result["source_shaped_unit_test"] is True and
                all(value is False for value in result["checks"].values()),
                "Diagnostic chain falsely promoted")
        checked.append([row["case_id"], row["candidate_id"]])
    entry = manifest["cases"][0]
    case = entry["case_id"]
    path = ROOT / ".runtime-work/c110454-update019-six-selected/rail_reference/primary"
    attempt, processing = path / "compatibility", path / "saved/v0001/processing.json"
    rejected = []
    reject("synthetic_as_original", lambda: audit(attempt, processing, case, "primary",
           entry["construction_sha256"], diagnostic=False), rejected)
    reject("wrong_construction", lambda: selected_entry(case, "primary", "0" * 64), rejected)
    reject("unselected_case", lambda: selected_entry(HERE.name + "__reference", "primary",
           entry["construction_sha256"]), rejected)
    source = {"video_frames.jsonl": sha(attempt / "video_frames.jsonl")}
    source.update({name + ".mkv": sha(attempt / (name + ".mkv")) for name in CAMERAS})
    decoded = {source[name + ".mkv"]: {"frames": 480, "rgb_sequence_sha256": "a" * 64}
               for name in CAMERAS}
    pixel = {"format": "c110454-original-pixel-review-v1", "case_id": case, "frames": 480,
             "source_kind": "source_shaped_unit_test", "reviewer": "CPU schema fixture",
             "method": "schema exercise only", "frame_map_sha256": source["video_frames.jsonl"],
             "legal_verdict_claimed": False,
             "views": {name: {"video_sha256": source[name + ".mkv"],
                              "rgb_sequence_sha256": "a" * 64,
                              "reviewed_frame_ids": list(range(480)),
                              "subjects_visible": [], "limitations": "Synthetic pixels; no visibility claim"}
                       for name in CAMERAS}}
    check_pixel_review(pixel, case, source, decoded, diagnostic=True)
    original_pixel_unit = copy.deepcopy(pixel)
    original_pixel_unit["source_kind"] = "original_native_camera_pixels"
    original_pixel_unit["views"]["overview"]["subjects_visible"] = [
        "ego_body", "roadway", TARGET["rail_reference"]]
    check_pixel_review(original_pixel_unit, case, source, decoded, diagnostic=False)
    reject("original_pixel_missing_participant", lambda: check_pixel_review(
           {**original_pixel_unit, "views": {**original_pixel_unit["views"], "overview":
                 {**original_pixel_unit["views"]["overview"], "subjects_visible": ["roadway"]}}},
           case, source, decoded, diagnostic=False), rejected)
    reject("diagnostic_pixel_promoted", lambda: check_pixel_review(
           {**pixel, "views": {**pixel["views"], "overview":
                 {**pixel["views"]["overview"], "subjects_visible": ["ego_body"]}}},
           case, source, decoded, diagnostic=True), rejected)
    reject("stale_camera_decode", lambda: check_pixel_review(
           {**pixel, "views": {**pixel["views"], "overview":
                 {**pixel["views"]["overview"], "rgb_sequence_sha256": "0" * 64}}},
           case, source, decoded, diagnostic=True), rejected)
    reject("missing_camera", lambda: check_pixel_review(
           {**pixel, "views": {k: v for k, v in pixel["views"].items() if k != "overview"}},
           case, source, decoded, diagnostic=True), rejected)
    context = {"format": "c110454-original-road-context-review-v1", "case_id": case,
               "source_kind": "source_shaped_unit_test", "reviewer": "CPU schema fixture",
               "method": "schema exercise only",
               "road_geometry_sha256": sha(attempt / "road_geometry.json"),
               "road_xodr_sha256": sha(attempt / "road.xodr"),
               "statutory_or_traversal_context_sha256": sha(attempt / "statutory_context.json"),
               "native_map_sha256": json.loads((attempt / "road_geometry.json").read_text())["native_map_sha256"],
               "designation_confirmed": False, "legal_verdict_claimed": False}
    check_context_review(context, attempt, case, diagnostic=True)
    original_context_schema_branches = []
    for item in manifest["cases"]:
        branch_case = item["case_id"]
        branch_suffix = branch_case.removeprefix(HERE.name + "__")
        branch_attempt = (ROOT / ".runtime-work/c110454-update019-six-selected" /
                          branch_suffix / "primary/compatibility")
        branch_survey = json.loads((branch_attempt / "road_geometry.json").read_text())
        context_name = ("context.json" if branch_suffix.startswith("traversal_") else
                        "statutory_context.json")
        branch_review = {"format": "c110454-original-road-context-review-v1",
                         "case_id": branch_case, "source_kind": "original_native_map_and_scene",
                         "reviewer": "CPU unit schema only", "method": "source-shaped branch test",
                         "road_geometry_sha256": sha(branch_attempt / "road_geometry.json"),
                         "road_xodr_sha256": sha(branch_attempt / "road.xodr"),
                         "statutory_or_traversal_context_sha256": sha(branch_attempt / context_name),
                         "native_map_sha256": branch_survey["native_map_sha256"],
                         "designation_confirmed": True,
                         "zone_kind": ZONE_KIND[branch_suffix],
                         "observations": ["CPU unit schema only"],
                         "limitations": "Synthetic source; no original designation confirmed",
                         "legal_verdict_claimed": False,
                         "two_way_native_readback": True,
                         "one_way_native_readback": branch_survey.get("one_way_native_readback"),
                         "railroad_crossing_native_readback": branch_survey.get("railroad_crossing_native_readback")}
        check_context_review(branch_review, branch_attempt, branch_case, diagnostic=False)
        original_context_schema_branches.append(branch_suffix)
        if branch_suffix == "oneway_present":
            reject("original_oneway_designation_changed", lambda: check_context_review(
                   {**branch_review, "one_way_native_readback": False}, branch_attempt,
                   branch_case, diagnostic=False), rejected)
    reject("diagnostic_designation_promoted", lambda: check_context_review(
           {**context, "designation_confirmed": True}, attempt, case, diagnostic=True), rejected)
    reject("stale_road_context", lambda: check_context_review(
           {**context, "road_geometry_sha256": "0" * 64}, attempt, case, diagnostic=True), rejected)
    proof = {"format": "c110454-delivery-audit-cpu-proof-v1",
             "manifest_sha256": sha(HERE / "execution-manifest.json"),
             "diagnostic_chains_checked": len(checked),
             "original_schema_unit_branches": original_context_schema_branches,
             "original_native_audits_passed": 0,
             "rejected_mutations": rejected,
             "physical_or_legal_acceptance_claimed": False}
    (HERE / "update022-delivery-audit-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
