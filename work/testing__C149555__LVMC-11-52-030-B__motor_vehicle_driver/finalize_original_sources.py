"""Build the freight source packet from sealed original acquisition files.

This stage does not create a canonical Native result or accept a recording. It
joins the 20 Hz motion and FrameMap to independently sourced site, sign,
commercial and cargo facts for the later saved and delivery auditors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_contract import (SOURCE_FIELDS, SourceError, VARIANTS, audit_source_bundle,
                              derive_freight_activity, inside_posted_window, read_sealed)


ASSIGNMENT = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    require(path.is_file(), f"missing original acquisition: {path.name}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def finalize(attempt: Path, *, case_id: str, source_refs: dict) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    source_refs = dict(source_refs)
    require(case_id.startswith(ASSIGNMENT + "__"), "foreign freight case")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    require(variant in VARIANTS, "unknown exact freight case")
    required = set(SOURCE_FIELDS) - {"native_result", "freight_activity"}
    if "freight_activity" in source_refs:
        required.add("freight_activity")
    require(required | {"comparison_context"} <= set(source_refs), "missing original source reference")
    sources = {}
    for name in required | {"comparison_context"}:
        ref = source_refs[name]
        require(ref.get("path") and ref.get("sha256"), f"missing original source seal: {name}")
        path = (attempt / ref["path"]).resolve(strict=True)
        require(path.is_relative_to(attempt) and path.is_file(),
                f"original source escapes attempt: {name}")
        sources[name] = read_sealed(path, ref["sha256"])

    frame_map = rows(attempt / "frame-map.jsonl")
    motion = rows(attempt / "freight_motion.jsonl")
    require(len(frame_map) == len(motion) == 900, "900 synchronized original samples required")
    require(sources["frame_map"].get("case_id") == case_id and
            sources["frame_map"].get("frames") == list(range(900)),
            "original frame-index source mismatch")
    for index, (frame, sample) in enumerate(zip(frame_map, motion)):
        require(frame.get("video_frame") == sample.get("original_frame") == index,
                "original video/motion frame join mismatch")
        require(frame.get("native_frame") == sample.get("native_frame") and
                frame.get("time_s") == sample.get("time_s"),
                "original Native frame/time join mismatch")

    if "freight_activity" not in sources:
        activity = dict(vehicle_id=sources["commercial_dossier"].get("vehicle_id"),
                        **derive_freight_activity(motion))
        path = attempt / "freight_activity.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(activity, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        source_refs["freight_activity"] = {"path": str(path), "sha256": sha256(path)}
        sources["freight_activity"] = activity

    native_map = sources["native_map"]
    curb = sources["curb_observation"]
    sign = sources["sign_observation"]
    dossier = sources["commercial_dossier"]
    freight = sources["freight_activity"]
    civil_source = sources["civil_time"]
    context = sources["comparison_context"]
    require(context.get("case_id") == case_id, "comparison context case mismatch")
    require(context.get("civil_time_source_sha256") == source_refs["civil_time"]["sha256"],
            "comparison civil-time source mismatch")
    conditions = context.get("posted_conditions", {})
    require(conditions.get("verbatim_text") == sign.get("verbatim_text") and
            conditions.get("civil_windows") == sign.get("civil_windows") and
            conditions.get("freight_permitted") == sign.get("freight_permitted"),
            "comparison sign conditions differ from original source")
    require(context.get("zone") == {"start_station_m": curb.get("start_station_m"),
                                    "end_station_m": curb.get("end_station_m")},
            "comparison zone differs from original curb source")
    civil = dict(civil_source, source_sha256=source_refs["civil_time"]["sha256"])
    packet = {
        "case_id": case_id,
        "variant": variant,
        "map_name": native_map.get("map_name"),
        "native_map_readback": {key: native_map.get(key) for key in
                                ("native_road_id", "native_lane_id", "one_way_native_readback")},
        "one_way_native_readback": native_map.get("one_way_native_readback"),
        "curb_color_observed": curb.get("color"),
        "curb_observation": {key: curb.get(key) for key in
                             ("start_station_m", "end_station_m", "independent_pixel_review")},
        "sign_text_readback": sign.get("verbatim_text"),
        "sign_observation": {"independent_pixel_review": sign.get("independent_pixel_review")},
        "posted_conditions": conditions,
        "zone": context["zone"],
        "vehicle_id": dossier.get("vehicle_id"),
        "commercial_dossier": dossier,
        "freight_activity": freight,
        "civil_time": civil,
        "posted_window_check": {
            "source_sha256": hashlib.sha256((source_refs["sign_observation"]["sha256"] + ":" +
                                             source_refs["civil_time"]["sha256"]).encode()).hexdigest(),
            "derived_from_sign_sha256": source_refs["sign_observation"]["sha256"],
            "inside": inside_posted_window(civil, conditions),
        },
        "comparison_context_sha256": source_refs["comparison_context"]["sha256"],
        "frames": motion,
    }
    for name, field in SOURCE_FIELDS.items():
        if name != "native_result":
            packet[field] = source_refs[name]["sha256"]
    packet_path = attempt / "freight-native-source.json"
    with packet_path.open("x", encoding="utf-8") as stream:
        json.dump(packet, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    refs = dict(source_refs, native_result={"path": str(packet_path), "sha256": sha256(packet_path)})
    manifest = {"case_id": case_id, "kind": "delivery", "acquisition_kind": "original_native",
                "sources": refs,
                "raw_sources": {"frame_map": {"path": str(attempt / "frame-map.jsonl"),
                                              "sha256": sha256(attempt / "frame-map.jsonl")},
                                "motion": {"path": str(attempt / "freight_motion.jsonl"),
                                           "sha256": sha256(attempt / "freight_motion.jsonl")}}}
    audit_source_bundle(manifest, case_id=case_id, variant=variant,
                        source_root=attempt, require_raw=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-inventory", required=True, type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.source_inventory.read_text(encoding="utf-8"))
    manifest = finalize(args.attempt, case_id=args.case, source_refs=inventory["sources"])
    output = args.attempt / "freight-source-manifest.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(output)


if __name__ == "__main__":
    main()
