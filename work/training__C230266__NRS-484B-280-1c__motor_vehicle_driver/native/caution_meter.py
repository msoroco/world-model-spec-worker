"""Source-bound physical diagnostics for NRS 484B.280(1)(c).

The meter separates a documented driver observation from geometric visibility.
It makes no finding about whether the driver exercised proper caution.
"""

from __future__ import annotations

import hashlib
import json
import math

RATE = 20
FRAMES = 600


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(packet):
    require(packet.get("format") == "worker-pedestrian-caution-source-packet-v1", "Wrong source packet")
    require(packet.get("source_kind") in ("original_native_observation", "synthetic_native_sample"),
            "Unknown source kind")
    require(packet.get("law_id") == "NRS-484B-280-1c" and packet.get("cell_id") == "C230266",
            "Wrong law or cell")
    require(packet.get("actor") == "motor_vehicle_driver" and packet.get("pedestrian_id")
            and packet.get("vehicle_id") and packet["pedestrian_id"] != packet["vehicle_id"],
            "Distinct vehicle and pedestrian identities required")
    require(packet.get("pedestrian_classification_source") and packet.get("road_survey_source")
            and packet.get("driver_control_source"), "Classification, road and control sources required")
    trace = packet.get("trace")
    require(isinstance(trace, list) and len(trace) == FRAMES, "Full 600-frame source trace required")
    require(digest(trace) == packet.get("trace_sha256"), "Source trace hash mismatch")
    road = packet.get("road_y_bounds_m")
    require(isinstance(road, list) and len(road) == 2 and all(finite(v) for v in road)
            and road[0] < road[1], "Road boundary survey required")
    seen, visible, on_road, speeds, distances, ttcs = [], [], [], [], [], []
    first_observation = None
    for i, row in enumerate(trace):
        require(row.get("frame") == i and finite(row.get("time_s"))
                and abs(row["time_s"] - i / RATE) < 1e-8, "Frame and time join failed")
        for key in ("ego_x_m", "ego_y_m", "ped_x_m", "ped_y_m", "ego_speed_mps"):
            require(finite(row.get(key)), "Missing measured pose or speed")
        require(row["ego_speed_mps"] >= 0, "Negative measured speed")
        require(type(row.get("line_of_sight_clear")) is bool, "Visibility source missing")
        observation = row.get("driver_observed_pedestrian")
        require(type(observation) is bool, "Actual observation source missing")
        require(row.get("driver_observation_source") if observation else True,
                "Actual observation provenance missing")
        require(row.get("native_frame") is not None and row.get("video_frame") == i,
                "Native and video frame identities required")
        if observation and first_observation is None:
            first_observation = i
        seen.append(observation)
        visible.append(row["line_of_sight_clear"])
        on_road.append(road[0] <= row["ped_y_m"] <= road[1])
        speeds.append(row["ego_speed_mps"])
        distances.append(math.hypot(row["ego_x_m"] - row["ped_x_m"],
                                    row["ego_y_m"] - row["ped_y_m"]))
        closing = row["ped_x_m"] - row["ego_x_m"]
        ttcs.append(closing / row["ego_speed_mps"] if closing >= 0 and row["ego_speed_mps"] > 0 else None)
    require(any(on_road), "Pedestrian never on surveyed road")
    require(first_observation is not None, "No sourced actual observation")
    require(any(visible), "No sourced line of sight")
    return {
        "format": "worker-pedestrian-caution-measurement-v1",
        "source_kind": packet["source_kind"],
        "trace_sha256": packet["trace_sha256"],
        "frames": FRAMES,
        "rate_hz": RATE,
        "first_actual_observation_frame": first_observation,
        "visible_frames": sum(visible),
        "actual_observation_frames": sum(seen),
        "pedestrian_on_surveyed_road_frames": sum(on_road),
        "speed_at_first_observation_mps": speeds[first_observation],
        "speed_2s_after_observation_mps": speeds[min(first_observation + 40, FRAMES - 1)],
        "min_centre_distance_m": min(distances),
        "min_nonnegative_time_to_conflict_s": min((v for v in ttcs if v is not None), default=None),
        "proper_caution_legal_verdict": None,
        "actual_observation_proven": packet["source_kind"] == "original_native_observation",
        "physical_execution_proven": False,
    }
