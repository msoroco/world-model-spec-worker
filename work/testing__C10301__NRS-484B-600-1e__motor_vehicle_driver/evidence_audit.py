"""Verify frozen accepted inventory provenance without claiming speed coverage."""

import hashlib
import json
from pathlib import Path


def audit(repo: Path, assignment_id: str) -> dict:
    repo = Path(repo)
    inventory = json.loads((repo / "inputs" / assignment_id / "evidence.json").read_text())
    reviewed = []
    for item in inventory["recordings"]:
        membership = item["membership"]
        if membership.get("recording_id") != item["recording_id"] or membership.get("cell_id") != "C10301" or membership.get("law_id") != "NRS-484B-600-1e" or membership.get("actor") != "motor_vehicle_driver":
            raise ValueError("Accepted membership identity mismatch")
        for source in item["sources"]:
            path = repo / source["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError("Frozen accepted metadata hash mismatch")
            metadata = json.loads(path.read_text())
            for key in ("recording_id", "case_id", "cell_id", "law_id", "actor"):
                if metadata.get(key) != membership.get(key):
                    raise ValueError("Accepted metadata identity mismatch: " + key)
            if metadata.get("status") != "accepted" or metadata.get("reconstruction", {}).get("decoder_passed") is not True:
                raise ValueError("Accepted decode/registration not documented")
            reviewed.append({"recording_id": item["recording_id"],
                             "case_id": membership["case_id"],
                             "metadata_sha256": source["sha256"],
                             "frames": metadata.get("frames"),
                             "decoder_passed": True,
                             "physical_speed_and_public_way_equivalence": "unverified; original trace/video unavailable in standalone export"})
    if len(reviewed) != 3:
        raise ValueError("Expected all three accepted speed-boundary records")
    return {"format": "worker-accepted-speed-inventory-audit", "records": reviewed,
            "reuse_decision": "pending source-backed equivalence review; no accepted original replay"}
