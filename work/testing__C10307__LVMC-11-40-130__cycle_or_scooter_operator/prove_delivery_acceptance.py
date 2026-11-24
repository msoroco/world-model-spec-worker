"""CPU-only exact-case audit checker proof; never a physical acceptance receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from delivery_audit import CAMERAS, audit_delivery


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="c10307-delivery-check-") as folder:
        attempt = Path(folder)
        (attempt / "trace.jsonl").write_text(json.dumps({"frame": 100, "time_s": 0.05}) + "\n")
        (attempt / "video_frames.jsonl").write_text(json.dumps({"video_frame": 0, "carla_frame": 100,
                                                                  "time_s": 0.05}) + "\n")
        native = {"case_id": args.case, "diagnostic_fixture": False,
                  "trace_reference": "trace.jsonl", "video_frame_map_reference": "video_frames.jsonl",
                  "video_references": [name + ".mkv" for name in CAMERAS]}
        (attempt / "result.json").write_text(json.dumps(native))
        videos = {name: "a" * 64 for name in CAMERAS}
        saved = {"frame_count": 1, "cameras": {name: {"sha256": value} for name, value in videos.items()}}
        checks = {key: True for key in ("actual_bicycle_pixels", "rack_visible",
                  "human_powered_bicycle_classification", "municipal_jurisdiction",
                  "physical_route_completion", "full_episode_coverage")}
        if args.negative:
            checks["rack_visible"] = False
        review = {"format": "c10307-independent-physical-review-v1", "case_id": args.case,
                  "native_result_sha256": sha(attempt / "result.json"),
                  "video_frame_map_sha256": sha(attempt / "video_frames.jsonl"),
                  "videos": videos, "reviewer": "CPU checker fixture", "review_source": "synthetic-unit-test-only",
                  "checks": checks}
        review_path = attempt / "review.json"
        review_path.write_text(json.dumps(review))
        with patch("delivery_audit.audit_saved", return_value=saved), patch(
                "delivery_audit.audit_source_provenance", return_value={"manifest_sha256": "CPU fixture only"}):
            result = audit_delivery(attempt, args.case, review_path)
        if result["case_id"] != args.case or result["frame_count"] != 1:
            raise ValueError("CPU checker fixture did not bind exact case and frame")
        print("CPU-only audit checker positive passed; synthetic fixture is not physical acceptance")


if __name__ == "__main__":
    main()
