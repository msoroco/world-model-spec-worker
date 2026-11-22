"""Construct source-shaped CPU follower-response probes for C179480.

These probes sample engineering brake-gap settings. They are neither selected
cases nor claims about normal and reasonable movement under the statute.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from source_measurement import analyze  # noqa: E402

SOURCE = HERE / "fixtures/reference-sources"
OUTPUT = REPO / ".runtime-work/c179480-traffic-effect-sweep"
GAPS = (7.0, 9.5, 12.0)
RATE = 20
FOLLOWER_INITIAL_SPEED_MPS = 3.0
ENGINEERING_DECEL_MPS2 = 2.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)


def construct(rows: list[dict], gap_setting_m: float) -> list[dict]:
    if gap_setting_m not in GAPS:
        raise ValueError("Unreviewed engineering gap setting")
    if len(rows) != 600 or any(row.get("source_kind") != "synthetic_native_sample" for row in rows):
        raise ValueError("Expected 600 source-labeled diagnostic frames")
    result = copy.deepcopy(rows)
    x = result[0]["following_x_m"]
    speed = FOLLOWER_INITIAL_SPEED_MPS
    for index, row in enumerate(result):
        if index:
            previous_ego = result[index - 1]["ego_x_m"]
            current_ego = row["ego_x_m"]
            if current_ego < previous_ego:
                raise ValueError("Ego route reverses in traffic-effect probe")
            gap_before = previous_ego - x
            if gap_before <= gap_setting_m + speed * speed / (2 * ENGINEERING_DECEL_MPS2):
                speed = max(0.0, speed - ENGINEERING_DECEL_MPS2 / RATE)
            x += speed / RATE
        gap = row["ego_x_m"] - x
        if gap <= 0:
            raise ValueError("Diagnostic follower contacts or passes ego")
        row["following_x_m"] = round(x, 6)
        row["following_speed_mps"] = round(speed, 6)
        row["following_velocity_xyz_mps"] = [round(speed, 6), 0.0, 0.0]
        row["following_gap_m"] = round(gap, 6)
        row["sweep_source_kind"] = "synthetic_kinematic_probe"
        row["follower_brake_gap_setting_m"] = gap_setting_m
    return result


def build() -> dict:
    raw = [json.loads(line) for line in (SOURCE / "native-actors.jsonl").read_text().splitlines()]
    mapping = SOURCE / "video_frames.jsonl"
    rows_out = []
    for gap_setting in GAPS:
        folder = OUTPUT / ("gap-" + str(gap_setting).replace(".", "_"))
        folder.mkdir(parents=True, exist_ok=True)
        actor = folder / "native-actors.jsonl"
        probe_rows = construct(raw, gap_setting)
        actor.write_text(lines(probe_rows))
        frame_map = folder / "video_frames.jsonl"
        frame_map.write_bytes(mapping.read_bytes())
        measured = analyze(actor, frame_map)
        if (measured["sample_count"] != 600 or not measured["complete_stop_observed"]
                or not measured["roadway_lane_overlap_frames"]
                or measured["normal_reasonable_movement_impeded"] !=
                "independent_original_source_review_required"):
            raise ValueError("Source measurement did not preserve the statutory question")
        rows_out.append({
            "brake_gap_setting_m": gap_setting,
            "actor_source_sha256": sha(actor),
            "frame_map_sha256": sha(frame_map),
            "following_min_gap_m": measured["following_min_gap_m"],
            "following_speed_drop_mps": measured["following_speed_drop_mps"],
            "following_min_speed_mps": measured["following_min_speed_mps"],
            "first_follower_brake_frame": next(
                row["frame"] for row in probe_rows
                if row["following_speed_mps"] < FOLLOWER_INITIAL_SPEED_MPS),
            "roadway_stop_frame_count": len(measured["roadway_stop_frames"]),
            "legal_movement_judgment": measured["normal_reasonable_movement_impeded"],
        })
    if len({row["actor_source_sha256"] for row in rows_out}) != len(GAPS):
        raise ValueError("Sweep settings did not produce distinct source histories")
    return {
        "format": "c179480-traffic-effect-engineering-probe-v1",
        "passed": True,
        "assignment_id": HERE.name,
        "source_actor_sha256": sha(SOURCE / "native-actors.jsonl"),
        "source_frame_map_sha256": sha(mapping),
        "sample_rate_hz": RATE,
        "duration_s": len(raw) / RATE,
        "probe_rows": rows_out,
        "scope": "synthetic 600-frame CPU source/measurement probe; engineering settings are not legal thresholds or selected delivery cases",
        "original_native_observed": False,
        "physical_or_legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
