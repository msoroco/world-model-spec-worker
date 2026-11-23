"""Independent source-bound comparison checks for three headlamp probes."""
from __future__ import annotations

from lamp_probe import CASE_MODES


def audit(fixed: dict, measurements: dict[str, dict]) -> dict:
    """Check held Native setup hashes and measured lamp-state differences.

    `fixed` maps modes to a review packet with immutable map, footprint,
    blueprint, weather, camera and controller hashes. These are source hashes,
    not descriptions or requested flags. Original image inspection is separate.
    """
    if set(fixed) != set(CASE_MODES) or set(measurements) != set(CASE_MODES):
        raise ValueError("comparison needs all exact headlamp cases")
    keys = ("reviewed_map_sha256", "parking_polygon_sha256", "vehicle_blueprint_sha256",
            "weather_sha256", "camera_policy_sha256", "parking_controller_sha256")
    for mode in CASE_MODES:
        packet, result = fixed[mode], measurements[mode]
        if any(not packet.get(key) for key in keys):
            raise ValueError("missing fixed-condition source hash")
        if result.get("requested_mode") != mode or result.get("frame_count", 0) < 2:
            raise ValueError("missing exact original measurement")
        if result.get("parked_sample_count") != result["frame_count"]:
            raise ValueError("parked condition did not hold for full comparison")
        if not result.get("source_hashes", {}).get("actor-state.jsonl") or not result["source_hashes"].get("camera-frame-map.jsonl"):
            raise ValueError("missing original source seal")
    for key in keys:
        if len({fixed[mode][key] for mode in CASE_MODES}) != 1:
            raise ValueError("declared fixed condition changed: " + key)
    if measurements["unlit"]["low_beam_readback_count"] or measurements["unlit"]["high_beam_readback_count"]:
        raise ValueError("unlit case has lit headlamp readback")
    if measurements["low_beam"]["low_beam_readback_count"] != measurements["low_beam"]["frame_count"] or measurements["low_beam"]["high_beam_readback_count"]:
        raise ValueError("low beam readback not isolated")
    if measurements["high_beam"]["high_beam_readback_count"] != measurements["high_beam"]["frame_count"] or measurements["high_beam"]["low_beam_readback_count"]:
        raise ValueError("high beam readback not isolated")
    return {"format": "headlamp-comparison-cpu-audit-v1", "fixed_hashes": fixed["unlit"],
            "checked_cases": list(CASE_MODES), "readback_differences_confirmed": True,
            "unresolved": ["Original pixels, emitted intensity and beam aim require independent review.",
                           "This audit does not establish statutory compliance."]}
