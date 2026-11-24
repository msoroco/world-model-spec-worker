"""Independent raw-row audit of the synthetic corridor proof."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assignment_path = ROOT.parent.parent / "inputs" / ROOT.name / "assignment.json"
assignment = json.loads(assignment_path.read_text())
assert assignment["law"]["id"] == "NRS-484B-210-3"
assert "when such movement requires driving off the paved portion" in assignment["law"]["text"]
proof_path = ROOT / "corridor-proof.json"
proof = json.loads(proof_path.read_text())
assert proof["format"] == "c178778-source-bound-corridor-diagnostic-v1"
assert proof["selected"] is False and proof["accepted"] is False
audit = {"format": "c178778-independent-corridor-audit-v1", "passed": True,
         "assignment_sha256": digest(assignment_path), "proof_sha256": digest(proof_path),
         "cases": {}, "selected": False, "accepted": False}
for name, lead_y, ego_y, expected_margin, expected_off in (
    ("paved_available", 0.5, 2.6, 0.6, 0),
    ("paved_unavailable_local", 1.6, 4.2, -0.5, 181),
):
    folder = ROOT / "fixtures" / "corridor" / name
    source = json.loads((folder / "sources.json").read_text())
    assert source["kind"] == "synthetic_cpu_corridor"
    for file, expected_hash in source["sha256"].items():
        assert digest(folder / file) == expected_hash
    geo = json.loads((folder / "geometry.json").read_text())
    assert geo["paved_y_m"] == [-4.0, 4.0]
    assert geo["right_shoulder_paved"] is False
    rows = [json.loads(line) for line in (folder / "actors.jsonl").read_text().splitlines()]
    assert len(rows) == 600
    overlap = off = feasible = 0
    for index, row in enumerate(rows):
        assert row["frame"] == 1000 + index and row["time_s"] == index / 20
        assert row["actors"]["lead"]["x_m"] == 20 + index * 0.05
        assert row["actors"]["ego"]["x_m"] == index * 0.1
        assert row["actors"]["lead"]["y_m"] == lead_y
        assert row["actors"]["ego"]["y_m"] == ego_y
        if abs(row["actors"]["ego"]["x_m"] - row["actors"]["lead"]["x_m"]) > 4.5:
            continue
        overlap += 1
        off += int(ego_y + 0.9 > 4.0 or ego_y - 0.9 < -4.0)
        feasible += int(4.0 - 0.9 >= lead_y + 0.9 + 0.9 + 0.2)
    measured = proof["observed"][name]
    assert overlap == 181 and off == expected_off
    assert measured["right_pass_overlap_frames"] == overlap
    assert measured["off_paved_during_right_pass_frames"] == off
    assert measured["paved_right_corridor_feasible_frames"] == feasible
    assert measured["minimum_paved_corridor_margin_m"] == expected_margin
    assert measured["statutory_requires_condition"] == "unresolved"
    assert measured["physical_native_verified"] is False
    audit["cases"][name] = {"rows": len(rows), "right_pass_overlap": overlap,
                            "off_paved_overlap": off, "paved_corridor_feasible": feasible,
                            "source_sha256": source["sha256"]}
assert len(proof["negative_errors"]) == 4
path = ROOT / "corridor-audit.json"
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
print(json.dumps({"passed": True, "audit_sha256": digest(path)}, sort_keys=True))
