"""CPU protocol proof for all seven exact acceptance audit identities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from delivery_audit import CHECKS, OBSERVATIONS, ROOT, SOURCE, sha, verify_inputs


def fixture(attempt: Path, case_id: str):
    (attempt / "traffic_spec").mkdir()
    for name in ("ego-body-history.jsonl", "other-body-history.jsonl",
                 "road.xodr", *SOURCE.CAMERAS):
        (attempt / name).write_text("synthetic CPU protocol bytes: " + name + "\n")
    (attempt / "original-trace.jsonl").write_text("synthetic motion\n")
    (attempt / "raw.mkv").write_bytes(b"synthetic composed video protocol bytes")
    (attempt / "video_frames.jsonl").write_text(
        json.dumps({"video_frame": 0, "time_s": 0.0}) + "\n" +
        json.dumps({"video_frame": 1, "time_s": 0.05}) + "\n")
    core = {"scenes": [{"t": 0}, {"t": 50}]}
    (attempt / "traffic_spec" / "trace.json").write_text(json.dumps(core))
    names = ("ego-body-history.jsonl", "other-body-history.jsonl",
             "road.xodr", "video_frames.jsonl", *SOURCE.CAMERAS)
    source = {"diagnostic_fixture": False,
              "source_hashes": {name: sha(attempt / name) for name in names}}
    binding = {"original-trace.jsonl": sha(attempt / "original-trace.jsonl")}
    physical = {"case_id": case_id, "provenance_kind": "native",
                "diagnostic_fixture": False, "setup_confirmed": True,
                "maneuver_completed": True, "physical_checks": {
                    name: {"status": "met", "sources": binding}
                    for name in ("setup", "target", "maneuver", "attempt")}}
    pixels = {"format": "worker-original-pixel-review", "case_id": case_id,
              "diagnostic_fixture": False, "reviewer": "CPU protocol fixture",
              "video_sha256": sha(attempt / "raw.mkv"),
              "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
              "core_trace_sha256": sha(attempt / "traffic_spec" / "trace.json"),
              "observations": {name: {"visible": True, "frame": 1,
                                      "view": "approach", "description": "protocol only"}
                               for name in OBSERVATIONS}}
    decode = {"format": "source-decode", "passed": True,
              "video_sha256": sha(attempt / "raw.mkv"),
              "mapping_sha256": sha(attempt / "video_frames.jsonl"),
              "checks": {"frame_count": "all-decoded-frames"}, "frames": 2}
    return source, physical, pixels, decode, core


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", choices=tuple(ROOT.name + "__" + name for name in
                        ("precedence", "advance", "other_later", "opposite_straight",
                         "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")))
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="c125714-audit-proof-") as temp:
        attempt = Path(temp)
        source, physical, pixels, decode, core = fixture(attempt, args.case_id)
        if args.negative:
            pixels["video_sha256"] = "0" * 64
            try:
                verify_inputs(args.case_id, source, physical, pixels, decode, core, attempt)
            except ValueError as error:
                if str(error) != "original pixel review missing or stale":
                    raise
                raise ValueError(args.case_id + ": original pixel review missing or stale") from error
            raise AssertionError("stale original pixels accepted")
        audit = verify_inputs(args.case_id, source, physical, pixels, decode, core, attempt)
        if audit["checks"] != {name: True for name in CHECKS}:
            raise AssertionError("required acceptance check omitted")
        pixels["observations"]["other"]["visible"] = False
        try:
            verify_inputs(args.case_id, source, physical, pixels, decode, core, attempt)
        except ValueError as error:
            if str(error) != "actual pixels unverified: other":
                raise
        else:
            raise AssertionError("missing other participant pixels accepted")
        pixels["observations"]["other"]["visible"] = True
        core["scenes"][1]["t"] = 100
        try:
            verify_inputs(args.case_id, source, physical, pixels, decode, core, attempt)
        except ValueError as error:
            if str(error) != "Core trace and original frame time join differs":
                raise
        else:
            raise AssertionError("changed Core time accepted")
        core["scenes"][1]["t"] = 50
        (attempt / "original-trace.jsonl").write_text("changed synthetic motion\n")
        try:
            verify_inputs(args.case_id, source, physical, pixels, decode, core, attempt)
        except ValueError as error:
            if str(error) != "physical completion source changed: original-trace.jsonl":
                raise
        else:
            raise AssertionError("changed physical source accepted")
        print(args.case_id + ": diagnostic protocol positive and three negatives passed; no original acceptance")


if __name__ == "__main__":
    main()
