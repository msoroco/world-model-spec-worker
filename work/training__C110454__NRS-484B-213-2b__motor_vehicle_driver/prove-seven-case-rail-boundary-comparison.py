"""Compare the retained synthetic rail reference with the exact boundary probe."""
import hashlib
import json
from pathlib import Path

from camera_lifecycle_audit import audit as camera_audit
from saved_comparison_audit import normalize_config
from source_join_audit import read, require, rows, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update035-seven-case-probe-manifest.json"
RUNS = ROOT / ".runtime-work/c110454-update035-seven-probe"
PROOFS = HERE / "update035-probe-proofs"


def side(suffix):
    case = HERE.name + "__" + suffix
    entry = next(x for x in read(MANIFEST)["cases"] if x["case_id"] == case)
    attempt = RUNS / suffix / "primary/compatibility"
    saved = RUNS / suffix / "primary/saved/v0001"
    log = PROOFS / suffix / "primary/process-saved.log"
    selection = read(attempt / "candidate-selection.json")
    require(selection["manifest_sha256"] == sha(MANIFEST) and
            selection["construction_sha256"] == entry["construction_sha256"] and
            sha(HERE / entry["construction"]) == entry["construction_sha256"],
            "Selected candidate source changed")
    camera = camera_audit(attempt, log, case, "primary",
                          entry["construction_sha256"], diagnostic=True)
    require(camera["camera_source_shape_passed"] and not camera["passed"],
            "Source-shaped camera diagnostic changed")
    processed = read(saved / "processing.json")
    for name in ("road.xodr", "road_geometry.json", "statutory_context.json"):
        require(processed["original_source_hashes"][name] == sha(attempt / name),
                "Saved source hash changed: " + name)
    result = read(saved / "analysis/result.json")
    require(result["case_id"] == case and result["accepted"] is False and
            result["legal_verdict_claimed"] is False, "Synthetic result claimed acceptance")
    return {"case_id": case, "attempt": attempt, "saved": saved,
            "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"),
            "context": read(attempt / "statutory_context.json"),
            "road_sha256": sha(attempt / "road.xodr"),
            "samples": rows(attempt / "native_samples.jsonl"),
            "frames": rows(attempt / "video_frames.jsonl"),
            "measurements": result["measured_values"],
            "processing_sha256": sha(saved / "processing.json"),
            "source_join_sha256": camera["source_join_sha256"]}


left, at = side("rail_reference"), side("rail_at")
plan = read(HERE / "case-plan.json")
comparison = next(x for x in plan["comparisons"] if x["comparison_id"].endswith("__comparison_rail_at"))
require(comparison["case_ids"] == [left["case_id"], at["case_id"]] and
        comparison["deliberate_differences"] == ["railroad_grade_crossing_approach_distance"],
        "Planned comparison identity differs")
require(normalize_config(left["config"]) == normalize_config(at["config"]) and
        left["road"] == at["road"] and left["road_sha256"] == at["road_sha256"],
        "Held capture settings or road changed")
for key in ("railroad_crossing", "railroad_crossing_object_id", "one_way", "native_map_sha256"):
    require(left["context"][key] == at["context"][key],
            "Held railroad or map context changed: " + key)
require(len(left["samples"]) == len(at["samples"]) == len(left["frames"]) == len(at["frames"]) == 480,
        "Incomplete paired frame interval")
require(all(a["native_frame"] == b["native_frame"] and a["time_s"] == b["time_s"]
            for a, b in zip(left["samples"], at["samples"])) and
        left["frames"] == at["frames"], "Held frame/time or camera profile changed")
before = left["measurements"]["nearest_body_front_to_zone_m"]
boundary = at["measurements"]["nearest_body_front_to_zone_m"]
require(before > 30.48 and abs(boundary - 30.48) < 1e-6 and
        left["measurements"]["sampled_relation"] == "outside_100_ft" and
        at["measurements"]["sampled_relation"] == "within_100_ft",
        "Authored boundary relation differs")
proof = {"format": "c110454-rail-boundary-seven-case-diagnostic-v1",
         "manifest_sha256": sha(MANIFEST), "comparison_id": comparison["comparison_id"],
         "case_ids": comparison["case_ids"],
         "nearest_body_front_to_zone_m": {"rail_reference": before, "rail_at": boundary},
         "processing_sha256": [left["processing_sha256"], at["processing_sha256"]],
         "source_join_sha256": [left["source_join_sha256"], at["source_join_sha256"]],
         "synthetic_diagnostic": True, "original_comparison_accepted": False}
output = HERE / "update035-seven-case-rail-boundary-comparison-proof.json"
output.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"proof_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), **proof}))
