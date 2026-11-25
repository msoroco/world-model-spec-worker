"""Source-gated yellow-curb freight construction and original-history checks.

This module does not decide whether a particular stop complies with LVMC law.
It requests a scene through an injected Native adapter and checks recorded facts.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
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
    "civil_time": "civil_time_source_sha256",
}


def audit_source_bundle(manifest: dict, *, case_id: str, variant: str,
                        source_root: Path | None = None,
                        require_raw: bool = False) -> dict:
    """Read sealed original sources, join identities, then measure the packet.

    The manifest is a processor input, never a substitute for original bytes.
    Sources can be held outside the returned work tree during local capture.
    """
    entries = manifest.get("sources", {})
    _require(set(SOURCE_FIELDS) <= set(entries), "incomplete original source inventory")
    sources = {}
    if source_root is not None:
        source_root = source_root.resolve(strict=True)
    for name, field in SOURCE_FIELDS.items():
        ref = entries[name]
        _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"), f"missing source reference: {name}")
        path = Path(ref["path"])
        if source_root is not None:
            path = (source_root / path).resolve(strict=True)
            _require(path.is_relative_to(source_root) and path.is_file(),
                     f"original source escapes attempt: {name}")
        sources[name] = read_sealed(path, ref["sha256"])
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
    _require(sources["sign_observation"].get("civil_windows") == packet.get("posted_conditions", {}).get("civil_windows"),
             "posted civil windows differ from original sign source")
    _require(sources["sign_observation"].get("freight_permitted") == packet.get("posted_conditions", {}).get("freight_permitted"),
             "freight condition differs from original sign source")
    _require(sources["commercial_dossier"].get("vehicle_id") == packet.get("vehicle_id"), "commercial dossier vehicle mismatch")
    _require(sources["freight_activity"].get("vehicle_id") == packet.get("vehicle_id"), "activity source vehicle mismatch")
    _require(sources["civil_time"].get("timezone") == packet.get("civil_time", {}).get("timezone") and
             sources["civil_time"].get("local_datetime") == packet.get("civil_time", {}).get("local_datetime"),
             "original civil-time source mismatch")
    for name, fields in {
        "native_map": ("native_road_id", "native_lane_id", "one_way_native_readback"),
        "curb_observation": ("start_station_m", "end_station_m", "independent_pixel_review"),
        "sign_observation": ("independent_pixel_review",),
        "commercial_dossier": ("enterprise_use_reviewed", "qualifies_commercial"),
        "freight_activity": ("observed_action", "cargo_actor_id", "observed_transfer_frames"),
    }.items():
        source = sources[name]
        target = packet.get({"native_map": "native_map_readback", "curb_observation": "curb_observation",
                             "sign_observation": "sign_observation", "commercial_dossier": "commercial_dossier",
                             "freight_activity": "freight_activity"}[name], {})
        _require(isinstance(target, dict), f"missing original {name} values")
        for field in fields:
            _require(field in source and field in target and source[field] == target[field],
                     f"original {name} field mismatch: {field}")
    _require(sources["curb_observation"]["independent_pixel_review"] is True,
             "original curb pixel review missing")
    _require(sources["sign_observation"]["independent_pixel_review"] is True,
             "original sign pixel review missing")
    _require(packet.get("civil_time", {}).get("source_sha256") == entries["civil_time"]["sha256"],
             "civil-time source seal mismatch")
    if require_raw:
        _require(source_root is not None, "original attempt root required for raw sources")
        raw = manifest.get("raw_sources", {})
        _require(set(raw) == {"frame_map", "motion"}, "missing raw original acquisition")
        streams = {}
        for name in ("frame_map", "motion"):
            ref = raw[name]
            _require(ref.get("path") and ref.get("sha256"), f"missing raw source seal: {name}")
            path = (source_root / ref["path"]).resolve(strict=True)
            _require(path.is_relative_to(source_root) and path.is_file(),
                     f"raw original source escapes attempt: {name}")
            _require(_sha(path) == ref["sha256"], f"stale raw original source: {name}")
            streams[name] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        _require(len(streams["frame_map"]) == len(streams["motion"]) == 900,
                 "incomplete raw original acquisition")
        _require(streams["motion"] == packet.get("frames"),
                 "raw original motion differs from sealed Native packet")
        for index, (frame, sample) in enumerate(zip(streams["frame_map"], streams["motion"])):
            _require(frame.get("video_frame") == sample.get("original_frame") == index and
                     frame.get("native_frame") == sample.get("native_frame") and
                     frame.get("time_s") == sample.get("time_s"),
                     "raw original frame/time join mismatch")
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
    for field in ("native_result_sha256", "frame_map_sha256", "native_map_sha256", "curb_observation_sha256", "sign_observation_sha256", "commercial_dossier_sha256", "freight_activity_source_sha256", "civil_time_source_sha256"):
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
        body_min = frame.get("ego_body_station_min_m")
        body_max = frame.get("ego_body_station_max_m")
        _require(all(isinstance(v, (int, float)) and math.isfinite(v) for v in
                     (time_s, station, speed, body_min, body_max)), "invalid original motion/body sample")
        _require(body_min <= station <= body_max, "body footprint excludes ego station")
        _require(speed >= 0 and (previous_time is None or time_s > previous_time), "invalid original time/speed")
        if previous_time is not None:
            _require(abs(time_s - previous_time - 0.05) <= 0.001, "original 20 Hz timeline gap")
        previous_time = time_s
    zone = packet.get("zone", {})
    _require(zone.get("start_station_m", 0) < zone.get("end_station_m", 0), "invalid original zone")
    _require(frames[0]["ego_body_station_max_m"] < zone["start_station_m"],
             "original approach does not begin before zone")
    _require(any(f["ego_speed_mps"] > 0.5 for f in frames),
             "original approach motion missing")
    _require(frames[-1]["ego_station_m"] - frames[0]["ego_station_m"] > 1.0,
             "original approach made no progress")
    _require(all(f["ego_speed_mps"] <= 0.1 for f in frames[-40:]),
             "two-second final hold missing")
    final_hold_start = 899
    while final_hold_start > 0 and frames[final_hold_start - 1]["ego_speed_mps"] <= 0.1:
        final_hold_start -= 1
    stopped = [f for f in frames if f["ego_speed_mps"] <= 0.1]
    _require(stopped, "no original stop samples")
    inside = all(zone["start_station_m"] <= f["ego_body_station_min_m"] and
                 f["ego_body_station_max_m"] <= zone["end_station_m"] for f in stopped)
    outside = all(f["ego_body_station_max_m"] < zone["start_station_m"] or
                  f["ego_body_station_min_m"] > zone["end_station_m"] for f in stopped)
    _require(inside or outside, "stop spans zone boundary")
    activity = packet.get("freight_activity", {})
    _require(activity.get("vehicle_id") == packet["vehicle_id"], "activity/vehicle identity mismatch")
    observed = activity.get("observed_action")
    _require(observed in ("loading", "unloading", "none"), "freight action unobserved")
    derived = derive_freight_activity(frames)
    _require(observed == derived["observed_action"] and
             activity.get("cargo_actor_id") == derived["cargo_actor_id"] and
             activity.get("observed_transfer_frames") == derived["observed_transfer_frames"],
             "freight activity contradicts original cargo trajectory")
    if observed != "none":
        _require(activity.get("cargo_actor_id") and activity.get("observed_transfer_frames"), "freight transfer not evidenced")
        _require(all(isinstance(n, int) and 0 <= n < 900 for n in activity["observed_transfer_frames"]), "bad freight transfer frames")
        _require(all(frames[n]["ego_speed_mps"] <= 0.1 for n in activity["observed_transfer_frames"]),
                 "freight transfer did not occur during original halt")
    else:
        _require(not activity.get("observed_transfer_frames"),
                 "no-activity case contains original transfer frames")
    civil = packet.get("civil_time", {})
    _require(civil.get("source_sha256") and civil.get("timezone") and civil.get("local_datetime"), "civil clock source missing")
    _require(civil["source_sha256"] == packet["civil_time_source_sha256"], "civil-time source seal mismatch")
    window = packet.get("posted_window_check", {})
    _require(window.get("source_sha256") and window.get("derived_from_sign_sha256") == packet["sign_observation_sha256"], "posted window source mismatch")
    _require(isinstance(window.get("inside"), bool), "posted-window status unmeasured")
    _require(window["inside"] is inside_posted_window(civil, packet.get("posted_conditions", {})),
             "posted-window status contradicts sourced civil time and sign")
    return {"case_id": case_id, "variant": variant, "frames_checked": len(frames),
            "vehicle_id": packet["vehicle_id"], "observed_action": observed,
            "final_halt_original_frames": [final_hold_start, 899],
            "final_halt_duration_s": (900 - final_hold_start) / 20,
            "commercial_status_reviewed": packet["commercial_dossier"]["qualifies_commercial"],
            "stopped_inside_zone": inside, "stopped_outside_zone": outside,
            "inside_posted_window": window["inside"],
            "legal_conclusion": "unresolved; independent source review required"}


def derive_freight_activity(frames: list[dict]) -> dict:
    """Measure cargo direction from original pose samples, not case requests."""
    first_actor = frames[0].get("cargo_actor_id")
    if first_actor is None:
        _require(all(frame.get("cargo_actor_id") is None and
                     frame.get("cargo_lateral_offset_m") is None for frame in frames),
                 "untracked original cargo actor")
        return {"observed_action": "none", "cargo_actor_id": None,
                "observed_transfer_frames": []}
    _require(all(frame.get("cargo_actor_id") == first_actor and
                 isinstance(frame.get("cargo_lateral_offset_m"), (int, float)) and
                 math.isfinite(frame["cargo_lateral_offset_m"]) for frame in frames),
             "incomplete original cargo trajectory")
    moved = []
    for index in range(1, len(frames)):
        delta = frames[index]["cargo_lateral_offset_m"] - frames[index - 1]["cargo_lateral_offset_m"]
        if abs(delta) > 0.05:
            moved.append(index)
    displacement = frames[-1]["cargo_lateral_offset_m"] - frames[0]["cargo_lateral_offset_m"]
    _require(len(moved) >= 2 and abs(displacement) > 0.5,
             "original freight transfer motion missing")
    _require(all(frames[index]["ego_speed_mps"] <= 0.1 for index in moved),
             "original cargo moved before halt")
    return {"observed_action": "unloading" if displacement > 0 else "loading",
            "cargo_actor_id": first_actor, "observed_transfer_frames": moved}


def inside_posted_window(civil: dict, conditions: dict) -> bool:
    """Evaluate only the sign's stated civil windows, without a legal cutoff."""
    try:
        instant = datetime.fromisoformat(civil["local_datetime"])
    except (KeyError, TypeError, ValueError) as error:
        raise SourceError("invalid sourced civil datetime") from error
    windows = conditions.get("civil_windows")
    _require(isinstance(windows, list) and windows, "missing original sign civil windows")

    def minute(value):
        _require(isinstance(value, str) and len(value) == 5 and value[2] == ":", "invalid sign civil window")
        try:
            hour, minute_value = int(value[:2]), int(value[3:])
        except ValueError as error:
            raise SourceError("invalid sign civil window") from error
        _require(0 <= hour < 24 and 0 <= minute_value < 60, "invalid sign civil window")
        return 60 * hour + minute_value

    now = 60 * instant.hour + instant.minute
    for window in windows:
        _require(isinstance(window, dict), "invalid sign civil window")
        days = window.get("weekdays")
        _require(isinstance(days, list) and days and all(type(day) is int and 0 <= day <= 6 for day in days),
                 "invalid sign weekdays")
        start, end = minute(window.get("start")), minute(window.get("end"))
        _require(start != end, "zero-length sign civil window")
        if start < end and instant.weekday() in days and start <= now < end:
            return True
        if start > end and ((instant.weekday() in days and now >= start) or
                            ((instant - timedelta(days=1)).weekday() in days and now < end)):
            return True
    return False


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
