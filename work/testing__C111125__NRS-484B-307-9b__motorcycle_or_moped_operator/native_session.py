"""Bind a reviewed exact site to original Native event acquisition.

The operator owns world settings, traffic actors, sensors and restoration. This
module copies original source packets into the attempt and destroys its ego.
It records four independently returned original camera frames on each event tick.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from original_capture import capture_original
from camera_capture import FourViewRecorder
from media_decode import audit_manifest
from signal_exception import construct_native, sealed, verify_site


def capture_events(session, site_path, case_id, attempt):
    site_path = Path(site_path)
    source_root = site_path.parent
    site_bytes = site_path.read_bytes()
    site = json.loads(site_bytes)
    if site.get("diagnostic_fixture") is not False or site.get("case_id") != case_id:
        raise ValueError("Reviewed exact Native site packet required")
    verify_site(site, source_root)
    attempt = Path(attempt)
    if not attempt.is_dir():
        raise ValueError("Materialized attempt directory required")
    reserved = {"native-site.json", "original-events.json", "event-receipt.json",
                "saved-manifest.json", "media-manifest.json", "media-receipt.json"} | {name + ".mkv" for name in
                                          ("overview", "approach", "reference_corner", "driver_reference")}
    source_paths = {}
    for key, ref in site["original_sources"].items():
        relative = Path(ref["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Original source path escapes site")
        if str(relative) in source_paths or str(relative) in reserved:
            raise ValueError("Duplicate or reserved original source path")
        source_paths[str(relative)] = sealed(ref, source_root)
    if any((attempt / name).exists() for name in reserved | set(source_paths)):
        raise ValueError("Original attempt source already exists")
    native = None
    recorder = None
    runtime_started = False
    runtime_used = False
    try:
        native = construct_native(site, source_root, session.world, session.carla,
                                  session.blueprint_library)
        if hasattr(session, "bind_native"):
            session.bind_native(native, site)
        (attempt / "native-site.json").write_bytes(site_bytes)
        for relative, source in source_paths.items():
            target = attempt / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        if hasattr(session, "start_runtime_capture"):
            session.start_runtime_capture(attempt, case_id)
            runtime_started = True
            runtime_used = True
        recorder = FourViewRecorder(attempt, session.camera_adapter, case_id)
        receipt = capture_original(site, attempt, session.event_adapter,
                                   attempt / "original-events.json", on_frame=recorder.record)
        media_ref = recorder.finish()
        decoded = audit_manifest(attempt, media_ref, attempt / "media-receipt.json")
        if runtime_started:
            session.close_runtime_capture(confirmed=True)
            runtime_started = False
        if runtime_used:
            rows = json.loads((attempt / "original-events.json").read_text(encoding="utf-8"))
            frame_map = attempt / "video_frames.jsonl"
            if not frame_map.exists():
                frame_map.write_text("".join(json.dumps({"video_frame": i, "carla_frame": row["frame"],
                                                        "native_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
                                             for i, row in enumerate(rows)), encoding="utf-8")
            (attempt / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": False,
                "source_site_sha256": hashlib.sha256(site_bytes).hexdigest()}, indent=2) + "\n")
        source_keys = {"map": "map_ref", "route": "route_ref", "signal": "signal_ref",
                       "stop_reference": "stop_ref", "crosswalk": "crosswalk_ref"}
        sources = {name: site["original_sources"][site[key]] for name, key in source_keys.items()}
        sources["original_events"] = receipt["event_ref"]
        cause_key = site.get("cause_source_ref")
        if cause_key is not None:
            sources["cause"] = site["original_sources"][cause_key]
        media_manifest = json.loads((attempt / "media-manifest.json").read_text(encoding="utf-8"))
        camera_views = {}
        for name, view in media_manifest["camera_views"].items():
            camera_views[name] = dict(view, decoded_frames=decoded["camera_views"][name]["decoded_frames"],
                                      fps=decoded["camera_views"][name]["fps"])
        saved_manifest = {"assignment_id": case_id.rsplit("__", 1)[0], "case_id": case_id,
                          "law_id": "NRS-484B-307-9b", "actor": "motorcycle_or_moped_operator",
                          "fps": 20, "duration_frames": receipt["frame_count"],
                          "official_head_id": site["official_head_id"], "actor_id": receipt["actor_id"],
                          "sources": sources, "camera_views": camera_views,
                          "cause_status": site.get("unchanged_signal_cause", "not_established"),
                          "pixel_review_status": "pending", "physical_acceptance_claimed": False}
        saved_path = attempt / "saved-manifest.json"
        saved_bytes = (json.dumps(saved_manifest, sort_keys=True, indent=2) + "\n").encode()
        saved_path.write_bytes(saved_bytes)
        receipt.update({"case_id": case_id,
                        "site_packet_sha256": hashlib.sha256(site_bytes).hexdigest(),
                        "original_source_sha256": {key: ref["sha256"] for key, ref in site["original_sources"].items()},
                        "camera_media_status": "four_original_views_recorded_unreviewed",
                        "media_manifest_ref": media_ref,
                        "saved_manifest_ref": {"path": saved_path.name,
                                               "sha256": hashlib.sha256(saved_bytes).hexdigest()}})
        (attempt / "event-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        return receipt
    finally:
        if runtime_started:
            session.close_runtime_capture(confirmed=False)
        if recorder is not None and not (attempt / "event-receipt.json").exists():
            recorder.abort()
        if native is not None:
            native["ego"].destroy()
