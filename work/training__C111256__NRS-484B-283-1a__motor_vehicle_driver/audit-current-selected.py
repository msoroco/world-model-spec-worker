"""Read-only audit of all selected current diagnostic source and saved receipts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "road_geometry.json",
           "capture/manifest.json", "capture/evidence.jsonl", "trace.jsonl",
           "body_history.jsonl", "overview.mkv", "approach.mkv",
           "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    matrix = read(HERE / "current-selected-matrix-proof.json")
    manifest = read(HERE / "execution-manifest.json")
    binding = read(HERE / "current-selected-binding.json")
    if (matrix["path_count"] != 16 or binding["prebind_manifest_sha256"] != matrix["manifest_sha256"]
            or binding["bound_manifest_sha256"] != sha(HERE / "execution-manifest.json")
            or binding["matrix_proof_sha256"] != sha(HERE / "current-selected-matrix-proof.json")):
        raise ValueError("Prebind/final selected manifest proof differs")
    counts = {"cases": 0, "candidates": 0, "saved_source_hashes": 0, "frame_joins": 0}
    for entry in manifest["cases"]:
        counts["cases"] += 1
        case = entry["case_id"].rsplit("__", 1)[1]
        for ident in ("primary", "fallback1", "fallback2", "fallback3"):
            path = matrix["paths"][case + "-" + ident]
            selected = entry if ident == "primary" else next(
                c for c in entry["candidates"] if c["id"] == ident)
            attempt = ROOT / path["attempt"]
            saved = ROOT / path["saved"] / "v0001/processing.json"
            retained = HERE / "selected-current-proofs" / case / ident
            receipt = read(retained / "compatibility.json")
            processing = read(retained / "processing.json")
            candidate = read(attempt / "candidate-selection.json")
            if (path["construction_sha256"] != selected["construction_sha256"]
                    or sha(HERE / selected["construction"]) != selected["construction_sha256"]
                    or candidate["manifest_sha256"] != matrix["manifest_sha256"]
                    or candidate["construction_sha256"] != selected["construction_sha256"]
                    or sha(retained / "compatibility.json") != path["receipt_sha256"]
                    or sha(retained / "processing.json") != path["processing_sha256"]
                    or sha(saved) != path["processing_sha256"]
                    or receipt["negative_removed"] != "road_geometry.json"
                    or not receipt["passed"] or not processing["passed"]
                    or not processing["recorded_only"] or not processing["originals_preserved"]
                    or processing["timestamp_joins"]["frames"] != 600):
                raise ValueError("Selected current receipt mismatch: " + case + "-" + ident)
            for source in SOURCES:
                if sha(attempt / source) != processing["original_source_hashes"].get(source):
                    raise ValueError("Original source changed: " + source)
                counts["saved_source_hashes"] += 1
            counts["candidates"] += 1
            counts["frame_joins"] += 600
    if counts != {"cases": 4, "candidates": 16, "saved_source_hashes": 176,
                  "frame_joins": 9600}:
        raise ValueError("Current matrix coverage incomplete")
    return {"format": "c111256-current-selected-independent-audit-v1", "passed": True,
            **counts, "manifest_sha256": sha(HERE / "execution-manifest.json"),
            "matrix_proof_sha256": sha(HERE / "current-selected-matrix-proof.json"),
            "original_native_or_legal_claimed": False}


if __name__ == "__main__":
    result = audit()
    path = HERE / "current-selected-independent-audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"audit_sha256": sha(path), **result}))
