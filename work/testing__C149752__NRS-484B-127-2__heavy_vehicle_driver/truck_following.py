"""Source-bound construction and measurements for the assigned truck pass cell.

This module does not classify statutory compliance. All measurements come from
original Native frame observations; intended controller settings are never
used as observed facts.
"""

from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass


FEET_PER_METRE = 3.280839895013123
MIN_QUALIFYING_WIDTH_M = 80 * 0.0254
STATUTORY_SPACE_M = 500 / FEET_PER_METRE


@dataclass(frozen=True)
class Case:
    suffix: str
    gap_target_m: float
    lead_width_target_m: float
    ego_width_target_m: float
    available_same_direction_lanes: int
    passing: bool = False
    entering_vehicle: bool = False
    circumstance: str = "ordinary"


CASES = (
    Case("gap_below_500ft", 145.0, 2.10, 2.10, 1),
    Case("gap_at_500ft", STATUTORY_SPACE_M, 2.10, 2.10, 1),
    Case("gap_above_500ft", 160.0, 2.10, 2.10, 1),
    Case("passing_completion", 145.0, 2.10, 2.10, 1, passing=True),
    Case("entering_vehicle", 155.0, 2.10, 2.10, 1, entering_vehicle=True),
    Case("two_available_lanes", 145.0, 2.10, 2.10, 2),
    Case("lead_below_80in", 145.0, 1.98, 2.10, 1),
    Case("subject_below_80in", 145.0, 2.10, 1.98, 1),
    Case("conditions_constrained", 145.0, 2.10, 2.10, 1, circumstance="constrained"),
)


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def finite_number(value: object, label: str) -> float:
    require(type(value) in (float, int) and math.isfinite(value), f"{label}: finite number required")
    return float(value)


def planned_construction(case: Case, lane_source: dict, blueprint_source: dict) -> dict:
    """Resolve a lazy Native construction only after independent map/blueprint readback.

    The caller must provide measured lane topology and width, not derive either
    from the authored one-way label. The result is an executable adapter plan:
    spawn coordinates and speed controller targets are still intents.
    """
    require(lane_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(lane_source.get("highway_public") is True, "public highway source required")
    lanes = lane_source.get("available_same_direction_lanes")
    require(type(lanes) is int and lanes == case.available_same_direction_lanes, "available lane count mismatch")
    road_lanes = lane_source.get("driving_lanes")
    require(isinstance(road_lanes, list) and road_lanes, "Native driving lane inventory required")
    observed_lanes = sum(1 for lane in road_lanes if
                         lane.get("available") is True and lane.get("connected") is True and
                         finite_number(lane.get("direction_dot"), "lane direction") > 0)
    require(observed_lanes == lanes, "Native lane geometry disagrees with count")
    require(lane_source.get("straight_connected_route") is True, "connected straight route required")
    require(lane_source.get("opposing_pass_lane") is True or not case.passing, "passing lane source required")
    require(blueprint_source.get("source_kind") == "native_blueprint_readback", "Native blueprint readback required")
    ego_width = finite_number(blueprint_source.get("subject_overall_width_m"), "subject width")
    lead_width = finite_number(blueprint_source.get("lead_overall_width_m"), "lead width")
    require(abs(ego_width - case.ego_width_target_m) < 0.04, "subject width target mismatch")
    require(abs(lead_width - case.lead_width_target_m) < 0.04, "lead width target mismatch")
    for identity in ("subject", "lead"):
        require(blueprint_source.get(f"{identity}_vehicle_class") in ("truck", "combination"), f"{identity} truck class required")
        require(isinstance(blueprint_source.get(f"{identity}_blueprint_id"), str) and
                blueprint_source[f"{identity}_blueprint_id"], f"{identity} Native blueprint ID required")
    require(case.gap_target_m > 0, "positive gap required")
    return {
        "subject": {"identity": "subject", "vehicle_class": blueprint_source["subject_vehicle_class"], "spawn_s_m": 0.0},
        "lead": {"identity": "lead", "vehicle_class": blueprint_source["lead_vehicle_class"], "spawn_s_m": case.gap_target_m + 12.0},
        "controller": {"kind": "source_gated_follow_or_pass", "subject_target_mps": 13.0, "lead_target_mps": 13.0,
                       "gap_target_m": case.gap_target_m, "pass_after_s": 20.0 if case.passing else None,
                       "entry_after_s": 23.0 if case.entering_vehicle else None},
        "map_source": lane_source,
        "blueprint_source": blueprint_source,
        "recording": {"fps": 20, "frames": 900, "camera_count": 4},
        "physical_risk": {"status": "physical" if case.passing else "none",
                          "reason": "Opposing-lane pass and return may fail on the selected map" if case.passing else "No identified special motion risk"},
    }


def execute_case(adapter, case: Case, lane_source: dict, blueprint_source: dict) -> dict:
    """Execute only source-validated spawn and controller calls on an injected Native adapter.

    The adapter owns CARLA world state and must snapshot/restore outside this
    function. No CARLA import or simulation happens in CPU tests.
    """
    plan = planned_construction(case, lane_source, blueprint_source)
    subject = adapter.spawn_vehicle(plan["subject"], blueprint_source["subject_blueprint_id"])
    lead = adapter.spawn_vehicle(plan["lead"], blueprint_source["lead_blueprint_id"])
    adapter.configure_following(subject, lead, plan["controller"])
    if case.passing:
        adapter.configure_pass_phase(subject, lead, plan["controller"]["pass_after_s"])
    if case.entering_vehicle:
        entrant_id = blueprint_source.get("entrant_blueprint_id")
        require(isinstance(entrant_id, str) and entrant_id, "entering vehicle blueprint source required")
        entrant = adapter.spawn_entrant(entrant_id, plan["controller"]["entry_after_s"])
    else:
        entrant = None
    return {"subject": subject, "lead": lead, "entrant": entrant, "capture_frames": plan["recording"]["frames"]}


def _body_interval(body: dict, identity: str) -> tuple[float, float]:
    require(body.get("identity") == identity, f"{identity} identity mismatch")
    vertices = body.get("route_vertex_s_m")
    require(isinstance(vertices, list) and len(vertices) == 8, f"{identity}: eight original body vertices required")
    points = [finite_number(v, f"{identity} route vertex") for v in vertices]
    return min(points), max(points)


def audit_original_frames(packet: dict, *, case_id: str, expected_frames: int = 900) -> dict:
    """Measure original-frame gap, width, lane count, entry and pass history.

    All 900 frames are required. No missing history is silently interpolated.
    A >500-ft measurement is a physical comparison, not a legal conclusion.
    """
    require(packet.get("source_kind") == "sealed_native_original_frames", "sealed Native source required")
    require(packet.get("case_id") == case_id, "case identity mismatch")
    frames = packet.get("frames")
    require(isinstance(frames, list) and len(frames) == expected_frames, "complete original frame sequence required")
    gaps = []
    widths = []
    lanes = []
    entries: set[str] = set()
    pass_phases = []
    previous_t = None
    for index, frame in enumerate(frames):
        require(frame.get("frame") == index, "original frame index discontinuity")
        time_s = finite_number(frame.get("time_s"), "original time")
        require(previous_t is None or time_s > previous_t, "original time discontinuity")
        require(abs(time_s - index / 20) < 0.002, "original 20 Hz time mapping required")
        previous_t = time_s
        bodies = frame.get("bodies")
        require(isinstance(bodies, list), "complete Native body inventory required")
        by_id = {b.get("identity"): b for b in bodies}
        require(len(by_id) == len(bodies) and "subject" in by_id and "lead" in by_id, "subject/lead body inventory required")
        subject_min, subject_max = _body_interval(by_id["subject"], "subject")
        lead_min, lead_max = _body_interval(by_id["lead"], "lead")
        require(lead_min >= subject_max or frame.get("pass_phase") in ("opposing", "ahead", "returned"), "lead must be ahead while following")
        if 14 <= time_s < 20:
            require(lead_min >= subject_max, "steady following gap unavailable")
            gaps.append(lead_min - subject_max)
        width_pair = []
        for identity in ("subject", "lead"):
            body = by_id[identity]
            require(body.get("vehicle_class") in ("truck", "combination"), "truck class source required")
            width_pair.append(finite_number(body.get("overall_width_m"), "body width"))
            require(body.get("mesh_width_verified") is True, "independent full mesh width verification required")
        widths.append(width_pair)
        lane_source = frame.get("lane_source")
        require(isinstance(lane_source, dict) and lane_source.get("source_kind") == "native_map_readback", "per-frame Native lane source required")
        require(lane_source.get("highway_public") is True, "public highway not established")
        same = lane_source.get("available_same_direction_lanes")
        require(type(same) is int and same >= 1, "available same-direction lane count required")
        driving_lanes = lane_source.get("driving_lanes")
        require(isinstance(driving_lanes, list) and driving_lanes, "Native driving lane inventory required")
        lane_ids = [item.get("lane_id") for item in driving_lanes]
        require(all(isinstance(item, str) and item for item in lane_ids) and len(set(lane_ids)) == len(lane_ids),
                "unique Native driving lane identities required")
        measured_same = sum(1 for item in driving_lanes if
                            item.get("available") is True and item.get("connected") is True and
                            finite_number(item.get("direction_dot"), "lane direction") > 0)
        require(measured_same == same, "available lane count disagrees with Native lane geometry")
        lanes.append(same)
        phase = frame.get("pass_phase", "following")
        require(phase in ("following", "opposing", "ahead", "returned"), "unknown pass phase")
        pass_phases.append(phase)
        for identity, body in by_id.items():
            if identity in ("subject", "lead"):
                continue
            other_min, other_max = _body_interval(body, identity)
            if other_min > subject_max and other_max < lead_min:
                entries.add(identity)
    require(gaps, "steady 14..20s gap window missing")
    completed_pass = False
    if "opposing" in pass_phases:
        first = pass_phases.index("opposing")
        later = pass_phases[first + 1:]
        if "ahead" in later:
            second = first + 1 + later.index("ahead")
            completed_pass = "returned" in pass_phases[second + 1:]
    return {"case_id": case_id, "original_frame_count": len(frames), "steady_gap_min_m": min(gaps),
            "steady_gap_min_ft": min(gaps) * FEET_PER_METRE,
            "subject_width_min_m": min(pair[0] for pair in widths),
            "lead_width_min_m": min(pair[1] for pair in widths),
            "same_direction_available_lane_count_min": min(lanes),
            "same_direction_available_lane_count_max": max(lanes),
            "entered_gap_distinct_vehicle_count": len(entries),
            "subject_pass_completed": completed_pass,
            "legal_judgment": "unresolved"}


def audit_sealed_capture(path: Path, seal: dict, case_id: str, expected_frames: int = 900) -> dict:
    """Require a byte-bound original source before any measurement is accepted."""
    source = Path(path)
    require(source.is_file(), "original Native source file missing")
    raw = source.read_bytes()
    require(seal.get("source_sha256") == hashlib.sha256(raw).hexdigest(), "original Native source hash mismatch")
    require(seal.get("case_id") == case_id, "seal case mismatch")
    require(seal.get("frame_count") == expected_frames, "seal frame count mismatch")
    packet = json.loads(raw)
    result = audit_original_frames(packet, case_id=case_id, expected_frames=expected_frames)
    result["original_source_sha256"] = seal["source_sha256"]
    return result


def audit_comparison(left: dict, right: dict, *, fixed_fields: tuple[str, ...], varied_field: str) -> dict:
    """Reject missing source bindings and drift in measured fixed conditions."""
    for name, result in (("left", left), ("right", right)):
        require(result.get("original_source_sha256") and len(result["original_source_sha256"]) == 64,
                f"{name}: original source seal required")
        require(result.get("original_frame_count") == 900, f"{name}: complete original frames required")
        require(result.get("legal_judgment") == "unresolved", f"{name}: legal verdict must remain unresolved")
    require(left.get("case_id") != right.get("case_id"), "distinct exact cases required")
    for field in fixed_fields:
        require(field in left and field in right, f"fixed field missing: {field}")
        require(left[field] == right[field], f"fixed condition drift: {field}")
    require(varied_field in left and varied_field in right, "varied field missing")
    require(left[varied_field] != right[varied_field], f"declared difference not observed: {varied_field}")
    return {"case_ids": [left["case_id"], right["case_id"]], "fixed_fields_checked": list(fixed_fields),
            "varied_field_checked": varied_field, "legal_judgment": "unresolved"}
