"""Selected diagnostic protocol proof for independent delivery audit.

Positive mode uses an explicitly synthetic source-shaped fixture with mocked
site/measurement inputs. Negative mode proves the audit rejects diagnostic
provenance. Neither mode is an original delivery receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from delivery_audit import audit
from reviewed_scene import ASSIGNMENT, CAMERAS, VARIANTS


def put(root: Path, name: str, value) -> dict:
    path = root / name
    path.write_text(json.dumps(value) + "\n" if not isinstance(value, str) else value,
                    encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(case: str, mode: str) -> dict:
    if case not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact case required")
    if mode not in ("diagnostic-positive", "delivery-negative"):
        raise ValueError("unknown mode")
    suffix = case.removeprefix(ASSIGNMENT + "__")
    right = suffix == "slow_right_follower"
    immediate = suffix != "slow_middle_no_immediate_follower"
    passing = suffix == "slow_middle_passing"
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix="c147344-delivery-") as tmp:
        stage = Path(tmp)
        scene = {"map_sha256": "a" * 64, "rightmost_lane_id": "-1",
                 "actors": [{"lane_id": "-1" if right else "-2"}],
                 "requested_immediate_follower": immediate,
                 "requested_passing_slower_vehicle": passing}
        observations = [{"ego_in_extreme_right_lane": right,
                         "follower_immediately_behind_in_ego_lane": immediate,
                         "follower_closing_speed_mps": 3.0,
                         "passing_slower_vehicle_observed": passing} for _ in range(900)]
        frames = [{"frame": i, "native_frame": i + 100, "time_s": i / 20,
                   "camera_frames": {name: i + 100 for name in CAMERAS}}
                  for i in range(900)]
        receipt = {"case_id": case, "source_kind": "original_native_attempt",
                   "native_process_exit_code": 0, "owner_released": True,
                   "attempt_id": "synthetic-protocol-attempt",
                   "recording_id": "synthetic-protocol-recording",
                   "site_ref": {"path": "site.json", "sha256": "b" * 64}}
        receipt["frame_map_ref"] = put(stage, "frame-map.json", {
            "source_kind": "original_native_frame_map", "case_id": case, "frames": frames})
        receipt["trace_ref"] = put(stage, "trace.json", {"synthetic_protocol_fixture": True})
        receipt["relation_ref"] = put(stage, "relation.json", {"synthetic_protocol_fixture": True})
        receipt["video_refs"] = {name: put(stage, name + ".bin", "synthetic-pixels")
                                 for name in CAMERAS}
        seal = {"source_kind": "original_native_capture_seal", "case_id": case,
                "attempt_id": receipt["attempt_id"], "recording_id": receipt["recording_id"],
                "sources": {ref["path"]: ref["sha256"] for ref in
                            [receipt["site_ref"], receipt["frame_map_ref"],
                             receipt["trace_ref"], receipt["relation_ref"],
                             *receipt["video_refs"].values()]}}
        receipt["capture_seal_ref"] = put(stage, "seal.json", seal)
        probe = lambda path: {"nb_read_frames": "900", "r_frame_rate": "20/1",
                              "width": "960", "height": "540"}
        with patch("delivery_audit.plan", return_value=scene), patch(
                "delivery_audit.finalize", return_value={"observations": observations}):
            if mode == "delivery-negative":
                receipt["diagnostic_fixture"] = True
                audit(stage, receipt, probe)
                raise AssertionError("Diagnostic source was accepted")
            outcome = audit(stage, receipt, probe)
    if outcome["frames_checked"] != 900 or len(outcome["video_sha256"]) != 4:
        raise ValueError("diagnostic protocol missed frame/video checks")
    return {"case_id": case, "scope": "synthetic delivery audit protocol only",
            "positive_protocol_passed": True, "original_delivery_claimed": False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--mode", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.case, a.mode), sort_keys=True))


if __name__ == "__main__":
    main()
