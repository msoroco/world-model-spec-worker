"""Source-bound comparison of canonical selected C110454 primary attempts."""
import json
from pathlib import Path

from camera_lifecycle_audit import audit as camera_audit
from saved_comparison_audit import compare_sources
from source_join_audit import read, require, rows, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PAIRS = {"rail": ("rail_reference", "rail_contrast"),
         "oneway": ("oneway_absent", "oneway_present"),
         "traversal": ("traversal_reference", "traversal_contrast")}


def load_side(suffix, manifest, *, diagnostic):
    case = HERE.name + "__" + suffix
    entry = next(row for row in manifest["cases"] if row["case_id"] == case)
    require(entry["kind"] == "delivery" and
            sha(HERE / entry["construction"]) == entry["construction_sha256"],
            "Selected construction differs")
    attempt = ROOT / ".runtime-work/c110454-update019-six-selected" / suffix / "primary/compatibility"
    proof_dir = HERE / "update019-selected-proofs" / suffix / "primary"
    saved_log = proof_dir / "process-saved.log"
    proof = read(proof_dir / "proof.json")
    require(proof.get("manifest_sha256") == sha(MANIFEST) and
            proof.get("construction_sha256") == entry["construction_sha256"] and
            proof.get("process_saved_log_sha256") == sha(saved_log),
            "Selected proof binding differs")
    selection = read(attempt / "candidate-selection.json")
    require(selection.get("manifest_sha256") == sha(MANIFEST),
            "Selected attempt manifest differs")
    review = camera_audit(attempt, saved_log, case, "primary",
                          entry["construction_sha256"], diagnostic=diagnostic)
    saved = read(saved_log)
    source_paths = ("road_geometry.json", "road.xodr") + (("statutory_context.json",)
                   if suffix.startswith(("rail_", "oneway_")) else
                   ("context.json",) if suffix.startswith("traversal_") else ())
    require(all(saved.get("original_source_hashes", {}).get(name) == sha(attempt / name)
                for name in source_paths), "Selected comparison source hash differs")
    result = {"config": read(attempt / "config.json"),
              "road": read(attempt / "road_geometry.json"),
              "samples": rows(attempt / "native_samples.jsonl"),
              "evidence": rows(attempt / "capture/evidence.jsonl"),
              "frames": rows(attempt / "video_frames.jsonl"),
              "road_xodr_sha256": sha(attempt / "road.xodr"),
              "source_sha256": {name: sha(attempt / name) for name in source_paths},
              "joined_source_hashes": review["source_join_sha256"],
              "camera_source_sha256": {name: item["sha256"] for name, item in
                                       review["camera_sources"].items()},
              "saved_processing_sha256": sha(saved_log),
              "construction_sha256": entry["construction_sha256"]}
    if suffix.startswith(("rail_", "oneway_")):
        result["statutory"] = read(attempt / "statutory_context.json")
    if suffix.startswith("traversal_"):
        result["context"] = read(attempt / "context.json")
    return result


def audit_pair(kind, *, diagnostic=False):
    require(kind in PAIRS, "Unknown selected comparison")
    manifest = read(MANIFEST)
    a, b = PAIRS[kind]
    left = load_side(a, manifest, diagnostic=diagnostic)
    right = load_side(b, manifest, diagnostic=diagnostic)
    plan = read(HERE / "case-plan.json")
    comparison_id = HERE.name + "__comparison_" + kind
    comparison = next(row for row in plan["comparisons"]
                      if row["comparison_id"] == comparison_id)
    require(comparison["case_ids"] == [HERE.name + "__" + a, HERE.name + "__" + b],
            "Selected comparison cases differ")
    if kind == "traversal":
        require(left["context"] == right["context"],
                "Held surveyed traversal context differs")
    observed = compare_sources(kind, left, right)
    return {"format": "c110454-selected-source-comparison-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "manifest_sha256": sha(MANIFEST),
            "source_bindings": [{key: side[key] for key in
                                 ("source_sha256", "joined_source_hashes",
                                  "camera_source_sha256", "saved_processing_sha256",
                                  "construction_sha256")} for side in (left, right)],
            **observed, "source_comparison_passed": True,
            "diagnostic_fixture": diagnostic, "passed": False,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=PAIRS)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.kind, diagnostic=args.diagnostic), indent=2))
