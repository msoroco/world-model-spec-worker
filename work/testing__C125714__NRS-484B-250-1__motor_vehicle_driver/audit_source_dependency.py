"""Inventory frozen accepted-source references without inferring physical coverage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = "testing__C125714__NRS-484B-250-1__motor_vehicle_driver"
INPUT = REPO / "inputs" / ASSIGNMENT


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    evidence = json.loads((INPUT / "evidence.json").read_text(encoding="utf-8"))
    rows = []
    for entry in evidence["recordings"]:
        if len(entry["sources"]) != 1:
            raise ValueError("expected one frozen accepted metadata source per recording")
        source = entry["sources"][0]
        metadata_path = REPO / source["path"]
        if not metadata_path.is_file() or sha(metadata_path) != source["sha256"]:
            raise ValueError("frozen metadata bytes differ: " + entry["recording_id"])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (metadata["recording_id"] != entry["recording_id"] or
                metadata["case_id"] != entry["membership"]["case_id"] or
                metadata["acceptance"]["case_id"] != metadata["case_id"]):
            raise ValueError("frozen accepted case join differs")
        references = {}
        for name in ("trace_source", "video_source", "delivery_audit"):
            value = metadata["acceptance"][name]
            references[name] = {"path": value, "available_here": Path(value).is_file()}
        rows.append({"case_id": metadata["case_id"],
                     "recording_id": metadata["recording_id"],
                     "metadata_path": source["path"],
                     "metadata_sha256": source["sha256"],
                     "source_references": references})
    if len(rows) != 7 or len({row["case_id"] for row in rows}) != 7:
        raise ValueError("frozen seven-case inventory differs")
    review_files = sorted(str(path.relative_to(INPUT)) for path in
                          (INPUT / "review-context").rglob("*") if path.is_file())
    if review_files != ["review-context/README.md", "review-context/review.json"]:
        raise ValueError("review-context export changed; re-review sources")
    ranges = (INPUT / "judgment_ranges.json").read_text(encoding="utf-8")
    exact_range_mentions = {key: ranges.count(key) for key in ("C125714", "NRS-484B-250-1")}
    return {"format": "c125714-frozen-source-dependency-audit",
            "assignment_id": ASSIGNMENT,
            "evidence_sha256": sha(INPUT / "evidence.json"),
            "review_files": review_files,
            "reviewed_original_packet_present": any(
                p.name == "reviewed-context.json" and p.is_file() for p in ROOT.rglob("*")),
            "exact_judgment_range_mentions": exact_range_mentions,
            "accepted_metadata_count": len(rows),
            "original_media_or_audit_available_count": sum(
                int(ref["available_here"]) for row in rows
                for ref in row["source_references"].values()),
            "recordings": rows,
            "conclusion": "Accepted metadata is present, but referenced original trace, video, delivery audit, and reviewed site packet are unavailable in this checkout; no physical or legal coverage is inferred."}


if __name__ == "__main__":
    result = audit()
    (ROOT / "source-dependency-audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("accepted_metadata_count", "original_media_or_audit_available_count",
                       "reviewed_original_packet_present", "exact_judgment_range_mentions")},
                     sort_keys=True))
