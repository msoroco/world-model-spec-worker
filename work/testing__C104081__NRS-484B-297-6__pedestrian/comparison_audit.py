"""Independent source-bound comparison audit for prepared 297(6) cases.

This accepts only source packets labeled as original saved acquisition. Unit
tests use synthetic packets solely to exercise rejection branches. It makes no
legal or physical acceptance decision about impassability or due care.
"""

import hashlib
import json
from pathlib import Path


FIXED_KEYS = ("cell_id", "actor", "map_id", "pedestrian_blueprint",
              "traffic_plan_sha256", "camera_profile_sha256", "duration_frames")
VARIABLE_KEYS = ("intervening_barrier_present", "designated_lane_used",
                 "pedestrian_direction", "sidewalk_obstruction_end_m",
                 "sidewalk_obstruction_kind")
ALLOWED_DIFFS = {
    "intervening_area_condition": {"intervening_barrier_present", "designated_lane_used"},
    "travel_direction": {"pedestrian_direction"},
    "sidewalk_return_opportunity": {"sidewalk_obstruction_end_m"},
    "sidewalk_obstruction_type": {"sidewalk_obstruction_kind"},
}


def read_packet(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"source digest mismatch: {path}")
    packet = json.loads(raw)
    if packet.get("source_kind") != "original_saved_acquisition":
        raise ValueError("comparison requires original saved acquisition")
    for key in ("case_id", *FIXED_KEYS, *VARIABLE_KEYS):
        if packet.get(key) is None:
            raise ValueError(f"missing measured field: {key}")
    if packet["duration_frames"] <= 0:
        raise ValueError("empty measured frame history")
    if packet["pedestrian_direction"] not in (-1, 1):
        raise ValueError("invalid pedestrian direction")
    if not isinstance(packet["intervening_barrier_present"], bool):
        raise ValueError("barrier observation must be boolean")
    if not isinstance(packet["designated_lane_used"], bool):
        raise ValueError("lane-use observation must be boolean")
    return packet


def audit(plan: dict, sources: dict[str, dict]) -> dict:
    """Return comparison facts or reject missing/changed original evidence."""
    cases = {c["case_id"]: c for c in plan["cases"]}
    if set(sources) != set(cases):
        raise ValueError("source packets do not cover exact planned cases")
    packets = {}
    for case_id, binding in sources.items():
        packet = read_packet(Path(binding["path"]), binding["sha256"])
        if packet["case_id"] != case_id:
            raise ValueError("source packet case mismatch")
        packets[case_id] = packet
    return _audit_packets(plan, packets, sources)


def _audit_packets(plan: dict, packets: dict, sources: dict) -> dict:
    findings = []
    for comparison in plan["comparisons"]:
        comparison_id = comparison["comparison_id"]
        if comparison_id not in ALLOWED_DIFFS or len(comparison["case_ids"]) != 2:
            raise ValueError("unknown or malformed comparison")
        first, second = (packets[x] for x in comparison["case_ids"])
        for key in FIXED_KEYS:
            if first[key] != second[key]:
                raise ValueError(f"fixed condition changed: {comparison_id}: {key}")
        actual = {key for key in VARIABLE_KEYS if first[key] != second[key]}
        if actual != ALLOWED_DIFFS[comparison_id]:
            raise ValueError(f"comparison changed wrong variables: {comparison_id}: {sorted(actual)}")
        findings.append({"comparison_id": comparison_id, "case_ids": comparison["case_ids"],
                         "observed_differences": sorted(actual), "fixed_conditions_verified": list(FIXED_KEYS),
                         "source_sha256": [sources[x]["sha256"] for x in comparison["case_ids"]]})
    return {"status": "source_consistency_passed", "findings": findings,
            "legal_judgment": "unresolved", "physical_acceptance": "not_assessed"}


def audit_saved_attempts(plan: dict, attempt_roots: dict[str, str]) -> dict:
    """Run the independent comparison from exact sealed saved attempts.

    This branch accepts only original-shaped acquisition. Diagnostic fixture
    packets remain useful for unit tests but cannot enter an accepted comparison.
    """
    from saved_measurement import comparison_projection

    cases = {case["case_id"] for case in plan["cases"]}
    if set(attempt_roots) != cases:
        raise ValueError("saved attempts do not cover exact planned cases")
    packets = {}
    sources = {}
    for case_id, root in attempt_roots.items():
        packet = comparison_projection(Path(root), case_id)
        if packet["source_kind"] != "original_saved_acquisition":
            raise ValueError("comparison requires original saved acquisition")
        packets[case_id] = packet
        sources[case_id] = {"sha256": packet["source_packet_sha256"]}
    return _audit_packets(plan, packets, sources)
