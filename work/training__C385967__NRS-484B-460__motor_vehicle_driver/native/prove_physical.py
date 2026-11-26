"""Exercise source-bound angle parking physical outcomes with CPU fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from saved_angle import measure as measure_park
from saved_angle_activity import measure as measure_activity


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proof(letter, kind):
    action, condition = (letter.split("-", 1) if "-" in letter else ("park", letter))
    suffix = "" if action == "park" else action + "_"
    case = ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + condition
    spec = json.loads((HERE / f"selected-{letter}-fixture.json").read_text())
    measure = measure_park if action == "park" else measure_activity
    names = ("native_samples.jsonl", "body_history.jsonl", "video_frames.jsonl",
             "official_device.json", "road_geometry.json", "parking_context.json")
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c385967-physical-") as name:
        source = Path(name)
        for item in names:
            if kind == "missing_evidence" and item == "official_device.json":
                continue
            content = spec["files"][item]
            if kind == "incomplete_motion" and item == "native_samples.jsonl":
                rows = [json.loads(line) for line in content.splitlines()]
                for row in rows:
                    row["ego_speed_mps"] = 1.0
                content = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
            (source / item).write_text(content)
        hashes = {item: sha(source / item) for item in names if (source / item).exists()}
        try:
            reading = measure(source, case, allow_fixture=True)
            if kind != "complete_motion":
                raise ValueError("Negative physical fixture unexpectedly completed")
            status = "met"
            observed = {"mean_angle_to_curb_deg": reading["mean_measured_angle_to_curb_deg"],
                        "at_rest_frames": reading["at_rest_frames"]}
        except ValueError as error:
            if kind == "complete_motion":
                raise
            expected = ("Contiguous at-rest source interval absent" if kind == "incomplete_motion"
                        else "Missing required source: official_device.json")
            if expected not in str(error):
                raise
            status = "not_met" if kind == "incomplete_motion" else "unverified"
            observed = {}
    return {"format": "c385967-angle-physical-proof-v1", "case_id": case,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600 source-joined Native/body/camera frames and continuous at-rest angle measurement",
                "sources": hashes}}, "maneuver_completed": status == "met",
            "realized_observables": observed,
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "original_native_executed": False, "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("a", "b", "stop-a", "stop-b", "stand-a", "stand-b"), required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = proof(args.condition, args.kind)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": result["case_id"], "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"]}, sort_keys=True))
