"""Check the frozen accepted-recording inventory without claiming trace coverage."""

import hashlib
import json
from pathlib import Path


def audit(repo: Path, assignment_id: str) -> list[dict]:
    root = repo / "inputs" / assignment_id
    evidence = json.loads((root / "evidence.json").read_text())
    reviewed = []
    seen = set()
    for record in evidence["recordings"]:
        recording_id = record["recording_id"]
        if recording_id in seen:
            raise ValueError("duplicate recording ID: " + recording_id)
        seen.add(recording_id)
        if len(record["sources"]) != 1:
            raise ValueError("expected one frozen metadata source: " + recording_id)
        source = record["sources"][0]
        path = repo / source["path"]
        if path.resolve() != (root / "accepted" / recording_id / "metadata.json").resolve():
            raise ValueError("metadata path does not match recording ID: " + recording_id)
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("metadata hash mismatch: " + recording_id)
        metadata = json.loads(path.read_text())
        membership = record["membership"]
        for field in ("recording_id", "case_id", "law_id", "cell_id", "actor", "status"):
            if metadata[field] != membership[field]:
                raise ValueError("metadata/membership mismatch: " + recording_id + " " + field)
        if metadata["acceptance"]["frames"] != metadata["frames"]:
            raise ValueError("frame-count mismatch: " + recording_id)
        if not metadata["reconstruction"]["decoder_passed"]:
            raise ValueError("decoder not passed: " + recording_id)
        reviewed.append({
            "recording_id": recording_id,
            "case_id": metadata["case_id"],
            "frames": metadata["frames"],
            "decoder_passed": True,
            "source": source,
        })
    return reviewed


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[2]
    print(json.dumps(audit(repo, Path(__file__).resolve().parent.name), indent=2))
