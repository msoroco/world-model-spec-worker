"""Independent source-bound comparison checks for three headlamp probes."""
from __future__ import annotations

from lamp_probe import CASE_MODES
from delivery_audit import ASSIGNMENT, _contained, _sha, audit as audit_delivery
import json
from pathlib import Path


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


def audit_saved(attempts: dict, manifests: dict, fixed_packet_paths: dict,
                *, allow_diagnostic: bool = False) -> dict:
    """Recompute all three measurements and held conditions from sealed attempts.

    Each fixed packet binds six local source documents by content hash. The
    source documents can include reviewed map, vehicle, weather and controller
    details; text declarations alone do not count as a fixed-condition proof.
    """
    if any(set(mapping) != set(CASE_MODES) for mapping in
           (attempts, manifests, fixed_packet_paths)):
        raise ValueError("saved comparison requires all three exact cases")
    keys = ("reviewed_map_sha256", "parking_polygon_sha256", "vehicle_blueprint_sha256",
            "weather_sha256", "camera_policy_sha256", "parking_controller_sha256")
    fixed, measurements, delivery_hashes = {}, {}, {}
    for mode in CASE_MODES:
        root = Path(attempts[mode]).resolve()
        case_id = ASSIGNMENT + "__" + mode
        delivered = audit_delivery(root, manifests[mode], case_id=case_id,
                                   allow_diagnostic=allow_diagnostic)
        packet_path = Path(fixed_packet_paths[mode])
        if not packet_path.resolve().is_relative_to(root) or not packet_path.is_file():
            raise ValueError("fixed-condition packet must belong to attempt")
        packet = json.loads(packet_path.read_text())
        if packet.get("format") != "parked-headlamp-fixed-sources-v1" or packet.get("case_id") != case_id:
            raise ValueError("fixed-condition packet case identity mismatch")
        sources = packet.get("sources")
        if not isinstance(sources, dict) or set(sources) != set(keys):
            raise ValueError("all six fixed-condition sources required")
        fixed[mode] = {}
        for key in keys:
            item = sources[key]
            if not isinstance(item, dict):
                raise ValueError("fixed-condition source entry missing")
            path = _contained(root, item.get("path"))
            digest = _sha(path)
            if not path.stat().st_size or digest != item.get("sha256"):
                raise ValueError("fixed-condition source hash changed")
            fixed[mode][key] = digest
        measurements[mode] = delivered["observation"]
        delivery_hashes[mode] = {"native_receipt_sha256": delivered["native_receipt_sha256"],
                                 "media_hashes": delivered["media_hashes"]}
    result = audit(fixed, measurements)
    result["delivery_source_hashes"] = delivery_hashes
    result["saved_source_integrity_passed"] = True
    result["physical_acceptance_claimed"] = False
    return result
