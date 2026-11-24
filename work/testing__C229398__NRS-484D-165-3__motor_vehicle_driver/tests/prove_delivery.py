"""Exact-case CPU diagnostic of independent delivery source checks."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))
import delivery_audit as audit


def run(case_id, negative):
    if not case_id.startswith(audit.ASSIGNMENT + "__"):
        raise ValueError("wrong exact case")
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "result.json").write_text(json.dumps({
            "recording_description": {"channels": []},
            "trace_reference": "core.json", "video_frame_map_reference": "video_frames.jsonl"}))
        (root / "capture-seal.json").write_text(json.dumps({
            "format": "worker-sealed-capture", "provenance_kind": "native", "frames": 900,
            "restoration": {"restored": True},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "sources": {"result.json": audit.sha(root / "result.json")}}))
        (root / "video_frames.jsonl").write_text("".join(
            json.dumps({"video_frame": index, "time_s": index / 20}) + "\n"
            for index in range(900)))
        (root / "core.json").write_text(json.dumps({
            "scenes": [{"t": index * 50} for index in range(900)]}))
        (root / "primary.mkv").write_bytes(b"diagnostic video placeholder")
        review = root / "pixel-review.json"
        review.write_text(json.dumps({
            "case_id": case_id, "source_result_sha256": audit.sha(root / "result.json"),
            "video_sha256": audit.sha(root / "primary.mkv"),
            "frame_map_sha256": audit.sha(root / "video_frames.jsonl"),
            "reviewer": "CPU diagnostic", "method": "synthetic source-binding proof",
            "source_frames_reviewed": [0, 899], "parked_interval_verified": True,
            "diagnostic_fixture": True, "actual_original_pixels": False,
            "front_white_or_amber_500ft": "unknown", "rear_red_500ft": "unknown",
            "revelation_1000ft": "unknown", "traffic_side_installation": "unknown"}))
        receipt = root / "decode.json"

        def diagnostic_decode(*_args, **kwargs):
            Path(kwargs["receipt"]).write_text("{}\n")
            return {"auditor_sha256": "f" * 64}

        with patch.object(audit, "decode_video", side_effect=diagnostic_decode):
            result = audit.review(root, case_id, review, "primary.mkv", "core.json", receipt,
                                  diagnostic=not negative)
        if result["passed"] or result["physical_acceptance_claimed"]:
            raise ValueError("diagnostic cannot establish physical completion")
        print(json.dumps({"case_id": case_id, "software_checks": sorted(result["checks"]),
                          "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.case, args.negative)
