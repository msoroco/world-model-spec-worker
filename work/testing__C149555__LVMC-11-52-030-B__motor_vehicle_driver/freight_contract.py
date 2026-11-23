"""Source-gated yellow-curb freight construction and original-history checks.

This module does not decide whether a particular stop complies with LVMC law.
It requests a scene through an injected Native adapter and checks recorded facts.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


VARIANTS = {
    "freight_loading": {"activity": "loading", "commercial": True, "in_zone": True, "in_window": True},
    "freight_unloading": {"activity": "unloading", "commercial": True, "in_zone": True, "in_window": True},
    "no_freight_activity": {"activity": "none", "commercial": True, "in_zone": True, "in_window": True},
    "noncommercial_loading": {"activity": "loading", "commercial": False, "in_zone": True, "in_window": True},
    "outside_posted_time": {"activity": "loading", "commercial": True, "in_zone": True, "in_window": False},
    "outside_yellow_zone": {"activity": "loading", "commercial": True, "in_zone": False, "in_window": True},
}


class SourceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SourceError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_sealed(path: str | Path, expected_sha256: str) -> dict:
    path = Path(path)
    _require(path.is_file(), f"missing original source: {path}")
    _require(_sha(path) == expected_sha256, f"stale original source: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(result, dict), f"malformed original source: {path}")
    return result


SOURCE_FIELDS = {
    "native_result": "native_result_sha256",
    "frame_map": "frame_map_sha256",
    "native_map": "native_map_sha256",
    "curb_observation": "curb_observation_sha256",
    "sign_observation": "sign_observation_sha256",
    "commercial_dossier": "commercial_dossier_sha256",
    "freight_activity": "freight_activity_source_sha256",
}


def audit_source_bundle(manifest: dict, *, case_id: str, variant: str) -> dict:
    """Read sealed original sources, join identities, then measure the packet.

    The manifest is a processor input, never a substitute for original bytes.
    Sources can be held outside the returned work tree during local capture.
    """
    entries = manifest.get("sources", {})
    _require(set(SOURCE_FIELDS) <= set(entries), "incomplete original source inventory")
    sources = {}
    for name, field in SOURCE_FIELDS.items():
        ref = entries[name]
        _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"), f"missing source reference: {name}")
        sources[name] = read_sealed(ref["path"], ref["sha256"])
    packet = dict(sources["native_result"])
    # A source file cannot contain its own cryptographic digest. Bind it after
    # verifying its bytes against the outer manifest.
    packet["native_result_sha256"] = entries["native_result"]["sha256"]
    for name, field in SOURCE_FIELDS.items():
        if name == "native_result":
            continue
        _require(packet.get(field) == entries[name]["sha256"], f"packet/source seal mismatch: {name}")
    _require(sources["frame_map"].get("case_id") == case_id and sources["frame_map"].get("frames") == [f["original_frame"] for f in packet.get("frames", [])], "original frame-map identity mismatch")
    _require(sources["native_map"].get("map_name") == packet.get("map_name"), "Native map name mismatch")
    _require(sources["curb_observation"].get("color") == "yellow", "curb pixels do not support yellow")
    _require(sources["sign_observation"].get("verbatim_text") == packet.get("sign_text_readback"), "sign source/readback mismatch")
    _require(sources["commercial_dossier"].get("vehicle_id") == packet.get("vehicle_id"), "commercial dossier vehicle mismatch")
    _require(sources["freight_activity"].get("vehicle_id") == packet.get("vehicle_id"), "activity source vehicle mismatch")
    return audit_saved_original(packet, case_id=case_id, variant=variant)


def verify_site(site: dict) -> None:
    """Demand sourced physical surface and sign data before constructing a case."""
    _require(site.get("cell_id") == "C149555", "wrong cell")
    _require(site.get("layout") == "one_way_road", "wrong layout")
    _require(site.get("control") == "yellow_curb", "wrong curb control")
    for field in ("native_map_sha256", "native_road_id", "native_lane_id", "curb_observation_sha256", "sign_observation_sha256"):
        _require(bool(site.get(field)), f"missing sourced site field: {field}")
    _require(site.get("curb_color_observed") == "yellow", "yellow curb not observed")
    _require(site.get("sign_text_observed") == site.get("posted_conditions", {}).get("verbatim_text"), "sign text/readback mismatch")
    conditions = site.get("posted_conditions", {})
    _require(isinstance(conditions.get("civil_windows"), list) and conditions["civil_windows"], "missing posted civil windows")
    _require(conditions.get("freight_permitted") is True, "sign does not authorize freight")
    zone = site.get("zone", {})
    _require(zone.get("start_station_m", 0) < zone.get("end_station_m", 0), "invalid zone extent")
    _require(isinstance(site.get("approach_station_m"), (int, float)) and site["approach_station_m"] < zone["start_station_m"], "approach is not before zone")
    _require(isinstance(site.get("outside_station_m"), (int, float)) and site["outside_station_m"] > zone["end_station_m"], "outside-zone point overlaps zone")
    _require(site.get("one_way_native_readback") is True, "one-way Native readback missing")


def prepare_scene(adapter, site: dict, variant: str, commercial_dossier: dict) -> dict:
    """Execute the authored setup through a CARLA-capable adapter, without importing CARLA here.

    The adapter must validate its live map, spawn real world props and actors, and
    report readbacks; requesting these calls is not physical verification.
    """
    verify_site(site)
    _require(variant in VARIANTS, "unknown comparison variant")
    setting = VARIANTS[variant]
    _require(commercial_dossier.get("source_sha256"), "missing commercial-status source")
    _require(commercial_dossier.get("enterprise_use_reviewed") is True, "commercial-status review missing")
    _require(commercial_dossier.get("vehicle_id"), "missing subject vehicle identity")
    _require(commercial_dossier.get("qualifies_commercial") is setting["commercial"], "dossier/variant status mismatch")
    adapter.assert_native_map(site["native_map_sha256"])
    adapter.assert_one_way_lane(site["native_road_id"], site["native_lane_id"])
    adapter.assert_yellow_curb(site["zone"], site["curb_observation_sha256"])
    adapter.set_civil_clock_window(site["posted_conditions"], setting["in_window"])
    sign_id = adapter.spawn_or_verify_sign(site["posted_conditions"], site["sign_observation_sha256"])
    ego_id = adapter.spawn_vehicle(commercial_dossier["vehicle_id"], site["approach_station_m"])
    target = (site["zone"]["start_station_m"] + site["zone"]["end_station_m"]) / 2 if setting["in_zone"] else site["outside_station_m"]
    adapter.drive_to_station(ego_id, target)
    adapter.stop_and_hold(ego_id)
    cargo_id = None
    if setting["activity"] != "none":
        cargo_id = adapter.spawn_freight(site["freight_prop_blueprint"], site["zone"])
        adapter.transfer_freight(ego_id, cargo_id, setting["activity"])
    return {"ego_id": ego_id, "sign_id": sign_id, "cargo_id": cargo_id,
            "target_station_m": target, "variant": variant, "requested_activity": setting["activity"],
            "requested_civil_window": "inside" if setting["in_window"] else "outside"}


def audit_saved_original(packet: dict, *, case_id: str, variant: str) -> dict:
    """Check original-frame evidence and source identities; never use commanded targets."""
    _require(variant in VARIANTS, "unknown comparison variant")
    _require(packet.get("case_id") == case_id, "wrong original case")
    _require(packet.get("variant") == variant, "wrong original variant")
    for field in ("native_result_sha256", "frame_map_sha256", "native_map_sha256", "curb_observation_sha256", "sign_observation_sha256", "commercial_dossier_sha256", "freight_activity_source_sha256"):
        _require(packet.get(field), f"missing original source binding: {field}")
    _require(packet.get("curb_color_observed") == "yellow", "original yellow curb unverified")
    _require(packet.get("one_way_native_readback") is True, "original one-way lane unverified")
    _require(packet.get("sign_text_readback") == packet.get("posted_conditions", {}).get("verbatim_text"), "original sign text mismatch")
    _require(packet.get("vehicle_id") == packet.get("commercial_dossier", {}).get("vehicle_id"), "vehicle/dossier identity mismatch")
    _require(packet.get("commercial_dossier", {}).get("enterprise_use_reviewed") is True, "unreviewed commercial status")
    frames = packet.get("frames", [])
    _require(isinstance(frames, list) and len(frames) == 900, "900 original frames required")
    previous_time = None
    for index, frame in enumerate(frames):
        _require(frame.get("original_frame") == index, "noncontiguous original frame map")
        time_s = frame.get("time_s")
        station = frame.get("ego_station_m")
        speed = frame.get("ego_speed_mps")
        _require(all(isinstance(v, (int, float)) and math.isfinite(v) for v in (time_s, station, speed)), "invalid original motion sample")
        _require(speed >= 0 and (previous_time is None or time_s > previous_time), "invalid original time/speed")
        previous_time = time_s
    zone = packet.get("zone", {})
    _require(zone.get("start_station_m", 0) < zone.get("end_station_m", 0), "invalid original zone")
    stopped = [f for f in frames if f["ego_speed_mps"] <= 0.1]
    _require(stopped, "no original stop samples")
    stations = [f["ego_station_m"] for f in stopped]
    inside = all(zone["start_station_m"] <= s <= zone["end_station_m"] for s in stations)
    outside = all(s < zone["start_station_m"] or s > zone["end_station_m"] for s in stations)
    _require(inside or outside, "stop spans zone boundary")
    activity = packet.get("freight_activity", {})
    _require(activity.get("vehicle_id") == packet["vehicle_id"], "activity/vehicle identity mismatch")
    observed = activity.get("observed_action")
    _require(observed in ("loading", "unloading", "none"), "freight action unobserved")
    if observed != "none":
        _require(activity.get("cargo_actor_id") and activity.get("observed_transfer_frames"), "freight transfer not evidenced")
        _require(all(isinstance(n, int) and 0 <= n < 900 for n in activity["observed_transfer_frames"]), "bad freight transfer frames")
    civil = packet.get("civil_time", {})
    _require(civil.get("source_sha256") and civil.get("timezone") and civil.get("local_datetime"), "civil clock source missing")
    window = packet.get("posted_window_check", {})
    _require(window.get("source_sha256") and window.get("derived_from_sign_sha256") == packet["sign_observation_sha256"], "posted window source mismatch")
    _require(isinstance(window.get("inside"), bool), "posted-window status unmeasured")
    return {"case_id": case_id, "variant": variant, "frames_checked": len(frames),
            "vehicle_id": packet["vehicle_id"], "observed_action": observed,
            "commercial_status_reviewed": packet["commercial_dossier"]["qualifies_commercial"],
            "stopped_inside_zone": inside, "stopped_outside_zone": outside,
            "inside_posted_window": window["inside"],
            "legal_conclusion": "unresolved; independent source review required"}


def audit_comparison(left: dict, right: dict, changed_field: str) -> dict:
    """Reject uncontrolled scene differences in two source-bound saved packets."""
    _require(changed_field in {"freight_action", "commercial_status", "posted_window", "stop_zone"}, "unknown comparison variable")
    for field in ("native_map_sha256", "curb_observation_sha256", "sign_observation_sha256", "zone", "posted_conditions"):
        _require(left.get(field) == right.get(field), f"uncontrolled fixed condition: {field}")
    fixed = {"freight_action": ("commercial_dossier", "posted_window_check", "frames"),
             "commercial_status": ("freight_activity", "posted_window_check", "frames"),
             "posted_window": ("commercial_dossier", "freight_activity", "frames"),
             "stop_zone": ("commercial_dossier", "freight_activity", "posted_window_check")}[changed_field]
    for field in fixed:
        if field == "frames":
            # Motion is measured, so compare the stopped footprint rather than
            # command or exact simulator frame bytes.
            continue
        _require(left.get(field) == right.get(field), f"uncontrolled fixed condition: {field}")
    return {"left_case_id": left.get("case_id"), "right_case_id": right.get("case_id"),
            "deliberate_difference": changed_field, "fixed_conditions_checked": list(fixed) + ["native_map_sha256", "curb_observation_sha256", "sign_observation_sha256", "zone", "posted_conditions"]}


def require_case_completion(measured: dict) -> dict:
    """Check physical case target from saved measurements, separately from law."""
    variant = measured.get("variant")
    _require(variant in VARIANTS, "unknown case variant")
    target = VARIANTS[variant]
    _require(measured.get("frames_checked") == 900, "incomplete recorded duration")
    _require(measured.get("observed_action") == target["activity"], "freight action did not match case target")
    _require(measured.get("commercial_status_reviewed") is target["commercial"], "commercial status did not match case target")
    _require(measured.get("stopped_inside_zone") is target["in_zone"], "stopped footprint did not match case target")
    _require(measured.get("inside_posted_window") is target["in_window"], "posted-time relation did not match case target")
    return {"case_id": measured["case_id"], "physical_completion": True, "legal_conclusion": "unresolved"}
