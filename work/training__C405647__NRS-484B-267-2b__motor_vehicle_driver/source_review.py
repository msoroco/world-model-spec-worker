"""Join original emergency, lane, lamp, exception and hand-signal sources.

The diagnostic mode exercises source rejection without claiming that a synthetic
fixture establishes authorization, visibility, safety, or legal compliance.
"""
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "training__C405647__NRS-484B-267-2b__motor_vehicle_driver"
SOURCES = (
    "vehicle_authorization", "flashing_equipment", "flashing_qualification",
    "lamp_pixels", "lane_topology", "roadway_conditions", "traffic_conditions",
    "weather_conditions", "officer_direction", "hand_signal_pixels",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def join(folder, case_id, diagnostic=False):
    folder = Path(folder)
    review_path = folder / "emergency-review.json"
    if not review_path.is_file():
        raise ValueError("Missing required source: emergency-review.json")
    review = json.loads(review_path.read_text())
    if review.get("assignment_id") != ASSIGNMENT or review.get("case_id") != case_id:
        raise ValueError("Emergency source review identity differs")
    kind = review.get("review_kind")
    if kind != ("synthetic_diagnostic" if diagnostic else "original_native"):
        raise ValueError("Original Native emergency source review required")
    role = review.get("qualification_role")
    if role not in {"authorized_emergency", "official_regulatory"}:
        raise ValueError("Emergency or official regulatory role source missing")
    expected_role = "official_regulatory" if case_id.endswith("probe_03") else "authorized_emergency"
    if role != expected_role:
        raise ValueError("Selected qualification role differs from source review")
    refs = review.get("sources")
    if not isinstance(refs, dict) or set(refs) != set(SOURCES):
        raise ValueError("Incomplete emergency source inventory")
    joined = {}
    for name in SOURCES:
        ref = refs[name]
        path = f"source_context/{name}.txt"
        source = folder / path
        if not source.is_file():
            raise ValueError("Missing required source: " + path)
        if ref.get("path") != path or ref.get("sha256") != sha(source):
            raise ValueError("Emergency source hash differs: " + name)
        if not source.read_text().strip():
            raise ValueError("Empty emergency source: " + name)
        joined[name] = ref["sha256"]
    if not diagnostic:
        required = (
            "vehicle_authorized", "flashing_equipment_qualifies",
            "flashing_lamps_reviewed_in_original_pixels", "lane_graph_reviewed",
            "roadway_reviewed", "traffic_reviewed", "weather_reviewed",
            "officer_direction_reviewed", "hand_signal_visibility_reviewed",
        )
        if any(type(review.get(key)) is not bool for key in required):
            raise ValueError("Original emergency statutory activation review incomplete")
        if not all(review[key] for key in required[:7]):
            raise ValueError("Original emergency activation source not established")
        if not review["officer_direction_reviewed"]:
            raise ValueError("Original officer direction source not reviewed")
        if case_id.endswith("probe_04") and not review["hand_signal_visibility_reviewed"]:
            raise ValueError("Original visible hand signal source not reviewed")
    return {"review_kind": kind, "qualification_role": role, "review_sha256": sha(review_path),
            "source_sha256": joined, "source_reviewed": not diagnostic,
            "legal_result": None}
