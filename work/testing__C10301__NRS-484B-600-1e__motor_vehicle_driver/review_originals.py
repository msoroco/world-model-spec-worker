"""Inventory frozen accepted recording sources without inferring coverage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def inventory(metadata_path: Path) -> dict:
    metadata_path = Path(metadata_path)
    raw = metadata_path.read_bytes()
    data = json.loads(raw)
    acceptance = data["acceptance"]
    sources = []
    for label, path_key, hash_key in (
        ("trace", "trace_source", "trace_sha256"),
        ("video", "video_source", "video_sha256"),
        ("delivery_audit", "delivery_audit", "delivery_audit_sha256"),
    ):
        path = Path(acceptance[path_key])
        expected = acceptance[hash_key]
        present = path.is_file()
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if present else None
        sources.append({"kind": label, "source": str(path),
                        "expected_sha256": expected, "present": present,
                        "sha256_matches": actual == expected if present else None})
    return {"recording_id": data["recording_id"], "case_id": data["case_id"],
            "accepted_metadata_path": str(metadata_path),
            "accepted_metadata_sha256": hashlib.sha256(raw).hexdigest(),
            "sources": sources,
            "source_review_complete": all(s["sha256_matches"] is True for s in sources)}


def review(input_root: Path) -> dict:
    entries = [inventory(path) for path in sorted(Path(input_root).glob("accepted/*/metadata.json"))]
    if len(entries) != 3 or len({entry["case_id"] for entry in entries}) != 3:
        raise ValueError("Three distinct frozen accepted C10301 cases required")
    return {"format": "c10301-original-source-review-v1", "recordings": entries,
            "complete": all(entry["source_review_complete"] for entry in entries),
            "interpretation": "Source availability and byte identity only; no legal or physical coverage conclusion"}


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    inputs = here.parents[1] / "inputs" / here.name
    print(json.dumps(review(inputs), indent=2))
