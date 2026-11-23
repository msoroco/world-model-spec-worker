"""Exercise delivery evidence joins with labeled diagnostic bytes only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from delivery_audit import ASSIGNMENT, PIXELS, read, sha, verify_evidence


def fixture(root: Path, case: str):
    (root / "traffic_spec").mkdir()
    (root / "raw.mkv").write_bytes(b"diagnostic video bytes, not an original capture")
    (root / "video_frames.jsonl").write_text(
        json.dumps({"video_frame": 0, "time_s": 0.0}) + "\n" +
        json.dumps({"video_frame": 1, "time_s": 0.05}) + "\n")
    (root / "original-trace.jsonl").write_text("diagnostic original trace source\n")
    core = {"scenes": [{"t": 0}, {"t": 50}]}
    (root / "traffic_spec" / "trace.json").write_text(json.dumps(core))
    case_id = ASSIGNMENT + "__" + case
    source = {"case_id": case_id, "passed": True, "frames": 2,
              "frame_map_sha256": sha(root / "video_frames.jsonl")}
    decode = {"case_id": case_id, "passed": True, "video_sha256": sha(root / "raw.mkv")}
    binding = {"original-trace.jsonl": sha(root / "original-trace.jsonl")}
    physical = {"case_id": case_id, "provenance_kind": "native",
                "diagnostic_fixture": False, "setup_confirmed": True,
                "maneuver_completed": True, "physical_checks": {
        "setup": {"status": "met", "sources": binding},
        "target": {"status": "met", "sources": binding},
        "maneuver": {"status": "met", "sources": binding}}}
    pixels = {"format": "worker-original-pixel-review", "case_id": case_id,
              "video_sha256": sha(root / "raw.mkv"),
              "frame_map_sha256": sha(root / "video_frames.jsonl"),
              "core_trace_sha256": sha(root / "traffic_spec" / "trace.json"),
              "reviewer": "diagnostic-test-reviewer", "diagnostic_fixture": False,
              "observations": {key: {"visible": True, "frame": 1,
                                     "view": "approach", "description": "test join only"}
                               for key in PIXELS}}
    return case_id, source, decode, physical, pixels, core


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", choices=tuple(ASSIGNMENT + "__" + name for name in
                         ("near_stand", "far_stand", "near_stand_straight")))
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="taxi-delivery-proof-") as temp:
        root = Path(temp)
        case_id, source, decode, physical, pixels, core = fixture(
            root, args.case_id.removeprefix(ASSIGNMENT + "__"))
        if args.negative:
            pixels["video_sha256"] = "0" * 64
            try:
                verify_evidence(case_id, source, decode, physical, pixels, core, root)
            except ValueError as error:
                if str(error) != "original pixel review source changed":
                    raise
                raise ValueError(case_id + ": original pixel review source changed; rejection passed") from error
            raise AssertionError("stale pixel review accepted")
        audit = verify_evidence(case_id, source, decode, physical, pixels, core, root)
        if audit["checks"] != {key: True for key in (
                "native_source", "all_participants", "time_join", "full_video_decode",
                "actual_pixels", "physical_completion")}:
            raise AssertionError("audit omitted a required check")
        pixels["observations"]["posted_notice"]["visible"] = False
        try:
            verify_evidence(case_id, source, decode, physical, pixels, core, root)
        except ValueError as error:
            if str(error) != "actual pixels unverified: posted_notice":
                raise
        else:
            raise AssertionError("missing posted notice accepted")
        core["scenes"][1]["t"] = 100
        try:
            verify_evidence(case_id, source, decode, physical, pixels, core, root)
        except ValueError as error:
            if str(error) != "Core trace/original frame time join differs":
                raise
        else:
            raise AssertionError("changed Core timestamp accepted")
        core["scenes"][1]["t"] = 50
        (root / "original-trace.jsonl").write_text("changed diagnostic trace\n")
        try:
            verify_evidence(case_id, source, decode, physical, pixels, core, root)
        except ValueError as error:
            if str(error) != "physical completion source changed: original-trace.jsonl":
                raise
        else:
            raise AssertionError("stale physical source accepted")
        print(case_id + ": diagnostic positive and three negative invariants passed; no original capture claimed")


if __name__ == "__main__":
    main()
