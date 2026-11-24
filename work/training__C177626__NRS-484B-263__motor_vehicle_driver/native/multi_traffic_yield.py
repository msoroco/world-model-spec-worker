"""Source-bound diagnostic of all approaching highway traffic at an access point.

The configured time gap is a controller setting, never a statutory hazard or
reasonable-safety threshold. The returned measurements make no legal finding.
"""

from __future__ import annotations

from math import hypot, isfinite
from hashlib import sha256
import json

from controlled_access_yield import FRAME_COUNT, FRAME_RATE, control_request


def _actor(raw: dict, label: str) -> dict:
    keys = ("x_m", "y_m", "vx_mps", "vy_mps", "radius_m", "distance_to_conflict_m")
    try:
        values = {key: float(raw[key]) for key in keys}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing raw {label} actor state") from exc
    if not all(isfinite(value) for value in values.values()):
        raise ValueError(f"nonfinite raw {label} actor state")
    if values["radius_m"] <= 0 or values["distance_to_conflict_m"] < 0:
        raise ValueError(f"invalid raw {label} actor geometry")
    values["speed_mps"] = hypot(values["vx_mps"], values["vy_mps"])
    return values


def assess_trace(rows: list[dict], network: dict, policy: str) -> dict:
    """Check complete 20 Hz actor snapshots and derive per-vehicle gap history."""
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    if network.get("route_kind") not in ("entry", "exit"):
        raise ValueError("entry or exit route required")
    required = ("highway_source", "controlled_access_source", "access_lane_id",
                "highway_lane_id", "conflict_point_source", "actor_inventory_source")
    if not all(network.get(key) for key in required):
        raise ValueError("sourced controlled-access network and inventory required")
    if network["access_lane_id"] == network["highway_lane_id"]:
        raise ValueError("distinct access and highway lanes required")
    ids = network.get("approaching_vehicle_ids")
    if not isinstance(ids, list) or not ids or not all(
        isinstance(value, str) and value for value in ids
    ) or len(ids) != len(set(ids)):
        raise ValueError("nonempty unique approaching vehicle inventory required")

    minimum_gap = {actor_id: float("inf") for actor_id in ids}
    minimum_arrival_gap = {actor_id: float("inf") for actor_id in ids}
    maximum_deceleration = {actor_id: 0.0 for actor_id in ids}
    previous_speed: dict[str, float] = {}
    yield_request_frames = 0
    observed_yield_frames = 0
    traffic_present_frames = 0
    disagreements = 0
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        ego = _actor(row.get("ego", {}), "ego")
        traffic = row.get("traffic")
        if not isinstance(traffic, dict) or set(traffic) != set(ids):
            raise ValueError("approaching vehicle inventory missing from frame")
        if type(row.get("ego_yielding")) is not bool:
            raise ValueError("observed ego yield source required")
        observed_yield_frames += int(row["ego_yielding"])
        arrival_gaps = []
        present = False
        for actor_id in ids:
            raw = traffic[actor_id]
            other = _actor(raw, actor_id)
            if type(raw.get("on_highway")) is not bool or type(raw.get("approaching")) is not bool:
                raise ValueError("highway presence and approach source required")
            if raw["approaching"] and not raw["on_highway"]:
                raise ValueError("approaching highway vehicle must have highway source")
            minimum_gap[actor_id] = min(
                minimum_gap[actor_id],
                hypot(other["x_m"] - ego["x_m"], other["y_m"] - ego["y_m"])
                - other["radius_m"] - ego["radius_m"],
            )
            if actor_id in previous_speed:
                maximum_deceleration[actor_id] = max(
                    maximum_deceleration[actor_id],
                    (previous_speed[actor_id] - other["speed_mps"]) * FRAME_RATE,
                )
            previous_speed[actor_id] = other["speed_mps"]
            if raw["approaching"]:
                present = True
                if ego["speed_mps"] > 0 and other["speed_mps"] > 0:
                    gap = abs(
                        ego["distance_to_conflict_m"] / ego["speed_mps"]
                        - other["distance_to_conflict_m"] / other["speed_mps"]
                    )
                    arrival_gaps.append(gap)
                    minimum_arrival_gap[actor_id] = min(minimum_arrival_gap[actor_id], gap)
        traffic_present_frames += int(present)
        # A present actor with unmeasurable arrival time keeps the diagnostic
        # controller in yield mode; missing speed is not a measured safe gap.
        request = control_request(policy, min(arrival_gaps) if arrival_gaps else (0.0 if present else None))
        yield_request_frames += int(request["yield_request"])
        disagreements += int(request["yield_request"] != row["ego_yielding"])
    if traffic_present_frames == 0:
        raise ValueError("approaching highway traffic never observed")
    return {
        "source_kind": "raw_actor_network_diagnostic",
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "route_kind": network["route_kind"],
        "approaching_vehicle_ids": ids,
        "minimum_surface_gap_m_by_actor": minimum_gap,
        "minimum_projected_arrival_gap_s_by_actor": {
            actor_id: None if value == float("inf") else value
            for actor_id, value in minimum_arrival_gap.items()
        },
        "maximum_deceleration_mps2_by_actor": maximum_deceleration,
        "traffic_present_frames": traffic_present_frames,
        "controller_yield_request_frames": yield_request_frames,
        "observed_ego_yield_frames": observed_yield_frames,
        "controller_observation_disagreement_frames": disagreements,
        "legal_immediate_hazard_conclusion": None,
        "legal_reasonable_safety_conclusion": None,
    }


def compare_policies(rows: list[dict], network: dict) -> dict:
    """Run both engineering settings on identical source rows and network."""
    source_sha256 = sha256(json.dumps(
        {"rows": rows, "network": network}, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()
    early = assess_trace(rows, network, "earlier_yield")
    late = assess_trace(rows, network, "later_yield")
    assert early["minimum_surface_gap_m_by_actor"] == late["minimum_surface_gap_m_by_actor"]
    assert early["minimum_projected_arrival_gap_s_by_actor"] == late["minimum_projected_arrival_gap_s_by_actor"]
    return {
        "comparison_variable": "engineering_yield_request_gap_s",
        "fixed_source_sha256": source_sha256,
        "earlier_yield_request_frames": early["controller_yield_request_frames"],
        "later_yield_request_frames": late["controller_yield_request_frames"],
        "request_frame_difference": early["controller_yield_request_frames"] - late["controller_yield_request_frames"],
        "legal_comparison_conclusion": None,
    }
