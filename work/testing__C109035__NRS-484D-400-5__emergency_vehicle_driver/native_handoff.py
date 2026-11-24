"""Review-bound local source handoff for the exact emergency-device cases.

This validates source bytes before a Native connection. The reviewer documents
are local runtime inputs; the worker never supplies fabricated physical sources.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from camera_recorder import CAMERAS, PROFILE_SIZES
from emergency_scene import CASE_KNOBS
from native_capture import PREFIX
from original_adapters import OriginalInstrumentLog


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reviewed_file(path: Path, *, case_id: str, kind: str,
                   expected_sha256: str) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Reviewed source missing or symlinked: " + kind)
    raw = path.read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError("Reviewed source bytes differ: " + kind)
    obj = json.loads(raw)
    if (obj.get("case_id") != case_id or obj.get("source_kind") != kind or
            not obj.get("reviewer") or not obj.get("source_citation")):
        raise ValueError("Reviewed source identity or citation missing: " + kind)
    return obj


def _triplet(value, label: str) -> None:
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(item) not in (int, float) or not math.isfinite(item)
                for item in value)):
        raise ValueError("Reviewed camera pose invalid: " + label)


def validate_camera_plan(packet: dict) -> list[dict]:
    cameras = packet.get("cameras")
    if (not isinstance(cameras, list) or len(cameras) != 4 or
            [item.get("name") for item in cameras] != list(CAMERAS)):
        raise ValueError("Reviewed synchronized four-camera plan missing")
    for item in cameras:
        name = item["name"]
        if ((item.get("width"), item.get("height")) != PROFILE_SIZES[name] or
                item.get("attachment") not in ("world", "ego") or
                not item.get("reviewer") or not item.get("pose_source_citation") or
                type(item.get("fov_deg")) not in (int, float) or
                not 1 <= item["fov_deg"] <= 170):
            raise ValueError("Reviewed camera profile or citation differs: " + name)
        _triplet(item.get("location_xyz_m"), name + " location")
        _triplet(item.get("rotation_rpy_deg"), name + " rotation")
    return cameras


def validate_handoff(manifest_path: Path, *, case_id: str) -> dict:
    """Validate exact source hashes, roles and full instrument sequence.

    The manifest is a reviewer-authored local packet whose paths are absolute
    local files. It may not claim legal or physical acceptance.
    """
    if not case_id.startswith(PREFIX) or case_id[len(PREFIX):] not in CASE_KNOBS:
        raise ValueError("Unknown exact emergency case")
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Reviewed Native handoff missing or symlinked")
    packet = json.loads(manifest_path.read_bytes())
    if (packet.get("format") != "c109035-reviewed-native-handoff-v1" or
            packet.get("case_id") != case_id or
            packet.get("cell_id") != "C109035" or
            not packet.get("reviewer") or
            packet.get("physical_acceptance_claimed") is not False):
        raise ValueError("Reviewed Native handoff identity or scope differs")
    source_specs = packet.get("sources")
    required = ("site_packet", "dispatch_context", "equipment_record", "instrument_log")
    if not isinstance(source_specs, dict) or set(source_specs) != set(required):
        raise ValueError("Reviewed Native handoff source inventory incomplete")
    paths = {}
    documents = {}
    for kind in required:
        spec = source_specs[kind]
        if (not isinstance(spec, dict) or not isinstance(spec.get("path"), str) or
                not Path(spec["path"]).is_absolute() or
                not isinstance(spec.get("sha256"), str) or
                len(spec["sha256"]) != 64):
            raise ValueError("Reviewed Native source path or hash missing: " + kind)
        path = Path(spec["path"])
        paths[kind] = path
        if kind != "instrument_log":
            documents[kind] = _reviewed_file(
                path, case_id=case_id, kind=kind,
                expected_sha256=spec["sha256"])
    site = documents["site_packet"]
    validate_camera_plan(site)
    dispatch = documents["dispatch_context"]
    equipment = documents["equipment_record"]
    if (dispatch.get("source_status") != "documented" or
            dispatch.get("event") != CASE_KNOBS[case_id[len(PREFIX):]]["event"] or
            not dispatch.get("event_interval_frames")):
        raise ValueError("Reviewed dispatch event differs from exact case")
    if not equipment.get("authorization_source") or not equipment.get("device_installation_source"):
        raise ValueError("Reviewed authorization or device installation source missing")
    instrument_spec = source_specs["instrument_log"]
    if (instrument_spec.get("source_type") in (None, "", "command_echo") or
            not instrument_spec.get("source_citation")):
        raise ValueError("Independent instrument source missing")
    OriginalInstrumentLog(
        paths["instrument_log"], case_id=case_id,
        expected_sha256=instrument_spec["sha256"],
        source_type=instrument_spec["source_type"],
        source_citation=instrument_spec["source_citation"])
    return {"case_id": case_id, "packet_sha256": _sha(manifest_path.read_bytes()),
            "paths": paths, "source_specs": source_specs,
            "site": site, "dispatch": dispatch, "equipment": equipment,
            "physical_acceptance_claimed": False}
