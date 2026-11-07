"""Independent audit of C110454's saved synthetic traversal pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof_path = HERE / "traversal-cpu/proof.json"
    proof = json.loads(proof_path.read_text())
    if proof.get("status") != "cpu_proposal_not_native_capture" or proof.get("strict_delivery_ready") is not False:
        raise ValueError("Synthetic scope or readiness changed")
    plan = json.loads((HERE / "case-plan.json").read_text())
    expected = [ASSIGNMENT + "__traversal_reference", ASSIGNMENT + "__traversal_contrast"]
    cases = {case["case_id"]: case for case in plan["cases"]}
    comparison = next(c for c in plan["comparisons"] if c["comparison_id"] == ASSIGNMENT + "__comparison_traversal")
    if comparison["case_ids"] != expected or comparison["status"] != "planned_unverified":
        raise ValueError("Controlled comparison differs")
    counts = []
    for suffix in ("traversal_reference", "traversal_contrast"):
        case_id = ASSIGNMENT + "__" + suffix
        if cases[case_id]["source_topic_ids"] != ["text-0", "text-1"]:
            raise ValueError("Source topics differ")
        item = proof["cases"][suffix]
        path = HERE / item["saved_source"]
        if sha(path) != item["saved_sha256"]:
            raise ValueError("Saved source hash differs")
        rows = json.loads(path.read_text())
        if len(rows) != 480:
            raise ValueError("Saved frame count differs")
        moving = left = 0
        for i, row in enumerate(rows):
            if row["video_frame"] != i or row["native_frame"] != 1000 + i or abs(row["time_s"] - i / 20) > 1e-8:
                raise ValueError("Frame/time join differs")
            if row["source_kind"] != "synthetic_cpu_proposal" or row["two_way_native_survey"] is not True:
                raise ValueError("Synthetic source or two-way designation differs")
            points = row["body_xy_m"]
            if len(points) != 4 or any(len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
                raise ValueError("Full body differs")
            speed = row["speed_m_s"]
            if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
                raise ValueError("Saved speed differs")
            if min(p[0] for p in points) > -7 and max(p[0] for p in points) < 7 and speed > .05:
                moving += 1
                if min(p[1] for p in points) > 0:
                    left += 1
        measured = item["measure"]
        if (moving, left) != (measured["moving_traversal_frames"], measured["moving_left_traversal_frames"]):
            raise ValueError("Independent traversal measure differs")
        if not all(item["negative_proofs"].values()):
            raise ValueError("Negative proof absent")
        counts.append(left)
    if counts != [0, 39]:
        raise ValueError("Controlled left-side relation differs")
    return {"status": "passed", "scope": "saved synthetic CPU construction only",
            "proof_sha256": sha(proof_path), "case_ids": expected,
            "moving_left_traversal_frames": counts,
            "original_native_verified": False, "delivery_ready": False}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
