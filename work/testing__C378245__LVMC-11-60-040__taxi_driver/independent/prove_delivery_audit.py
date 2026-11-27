"""Exercise exact taxi delivery joins with test-only bytes, including rejection."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from delivery_audit import ASSIGNMENT, SUFFIXES, VIEWS, CHECKS, sha, verify


ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / ".runtime-work/c378245-taxi/delivery-audit-tests"


def fixture(root: Path, case: str):
    case_id = ASSIGNMENT + "__" + case
    (root / "physical-source.json").write_text('{"test_only":true}\n')
    rows = [{"video_frame": i, "time_s": i / 20} for i in range(900)]
    (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    for view in VIEWS:
        (root / (view + ".mkv")).write_bytes(("test-only-" + view).encode())
    source = {"case_id": case_id, "passed": True, "frames": 900,
              "frame_map_sha256": sha(root / "video_frames.jsonl")}
    decode = {"case_id": case_id, "passed": True,
              "videos": {view: {"frames": 900, "sha256": sha(root / (view + ".mkv"))}
                         for view in VIEWS}}
    physical = {"case_id": case_id, "provenance_kind": "native",
                "diagnostic_fixture": False, "maneuver_completed": True,
                "physical_checks": {name: {"status": "met",
                                     "sources": {"physical-source.json": sha(root / "physical-source.json")}}
                                    for name in ("setup", "target", "maneuver")}}
    pixels = {"format": "worker-original-pixel-review", "case_id": case_id,
              "diagnostic_fixture": False, "reviewer": "test-only-reviewer",
              "frame_map_sha256": sha(root / "video_frames.jsonl"),
              "video_sha256": sha(root / "overview.mkv"),
              "observations": {name: {"visible": True, "view": "overview",
                                     "frame": 450, "description": "test-only join"}
                               for name in ("taxi", "stand_boundary", "street_context", "passenger_door")}}
    activity = {"case_id": case_id, "diagnostic_fixture": False,
                "reviewer": "test-only-reviewer",
                "frame_map_sha256": sha(root / "video_frames.jsonl"),
                "actual_passenger_exchange": case.endswith(("load", "unload"))}
    core = {"scenes": [{"t": i * 50} for i in range(900)]}
    return case_id, source, decode, physical, pixels, activity, core


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", choices=[ASSIGNMENT + "__" + suffix for suffix in SUFFIXES])
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="taxi-delivery-proof-", dir=SCRATCH) as temp:
        root = Path(temp)
        evidence = list(fixture(root, args.case_id.removeprefix(ASSIGNMENT + "__")))
        if args.negative:
            evidence[4]["video_sha256"] = "0" * 64
            verify(*evidence[:1], root, *evidence[1:])
            raise AssertionError("changed original pixel binding accepted")
        audit = verify(evidence[0], root, *evidence[1:])
        if audit["checks"] != {key: True for key in CHECKS}:
            raise AssertionError("delivery check omitted")
        evidence[5]["actual_passenger_exchange"] = False
        if args.case_id.endswith(("__outside_stand_load", "__outside_stand_unload")):
            try:
                verify(evidence[0], root, *evidence[1:])
            except ValueError as error:
                if str(error) != "actual passenger exchange unverified":
                    raise
            else:
                raise AssertionError("absent passenger exchange accepted")
        print(args.case_id + ": diagnostic delivery joins passed; no original capture claimed")


if __name__ == "__main__":
    main()
