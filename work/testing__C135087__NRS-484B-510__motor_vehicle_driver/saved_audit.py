"""Independent read-only review of sealed source rows and four camera archives."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from native_capture import VIEWS
from reviewed_site import ROLES
from zone_audit import audit_original_frames


DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(attempt, case_id, expected_site_sha256, allow_diagnostic=False):
    """Verify bytes and joins; do not infer sight, interference or legality."""
    original = Path(attempt) / "original-attempt"
    seal_path = original / "seal.json"
    site_path = original / "site-packet.json"
    if not seal_path.is_file() or not site_path.is_file():
        raise ValueError("sealed original attempt missing")
    seal = json.loads(seal_path.read_text())
    packet = json.loads(site_path.read_text())
    if seal.get("case_id") != case_id or packet.get("case_id") != case_id:
        raise ValueError("original case mismatch")
    if seal.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot satisfy original saved audit")
    if not expected_site_sha256 or seal.get("site_packet_sha256") != expected_site_sha256 or \
            _sha(site_path.read_bytes()) != expected_site_sha256:
        raise ValueError("independent reviewed site hash mismatch")
    sources = packet.get("sources", {})
    if set(sources) != set(ROLES):
        raise ValueError("reviewed site source roles incomplete")
    for role, item in sources.items():
        path = original / item["path"]
        if not path.is_file() or _sha(path.read_bytes()) != item["sha256"]:
            raise ValueError("saved reviewed source missing or stale: " + role)
    measured = audit_original_frames(original / "history.jsonl", original / "context.json",
                                     seal_path, case_id)
    rows = [json.loads(line) for line in (original / "history.jsonl").read_text().splitlines()]
    if len(rows) != 900:
        raise ValueError("incomplete original pixel history")
    trace_path = Path(attempt) / "trace.jsonl"
    mapping_path = Path(attempt) / "video_frames.jsonl"
    if not trace_path.is_file() or not mapping_path.is_file() or \
            _sha(trace_path.read_bytes()) != seal.get("trace_sha256") or \
            _sha(mapping_path.read_bytes()) != seal.get("video_frame_map_sha256"):
        raise ValueError("original trace/video map missing or stale")
    traces = [json.loads(line) for line in trace_path.read_text().splitlines()]
    mappings = [json.loads(line) for line in mapping_path.read_text().splitlines()]
    if len(traces) != 900 or len(mappings) != 900:
        raise ValueError("incomplete original trace/video join")
    for index, (row, trace, mapping) in enumerate(zip(rows, traces, mappings)):
        if trace.get("frame") != row.get("native_frame") or \
                trace.get("time_s") != row.get("source_time_s") or \
                mapping.get("video_frame") != index or \
                mapping.get("carla_frame") != row.get("native_frame") or \
                mapping.get("time_s") != row.get("source_time_s"):
            raise ValueError("original trace/video frame join mismatch")
    for name in (*VIEWS, "raw"):
        path = Path(attempt) / (name + ".mkv")
        if not path.is_file() or _sha(path.read_bytes()) != seal.get("encoded_media_sha256", {}).get(name):
            raise ValueError("original encoded media missing or stale: " + name)
    decoded = {}
    for view in VIEWS:
        path = original / (view + ".zip")
        if not path.is_file() or _sha(path.read_bytes()) != seal.get("camera_archives_sha256", {}).get(view):
            raise ValueError("camera archive missing or stale: " + view)
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            if len(members) != 900 or len(set(members)) != 900:
                raise ValueError("incomplete original camera pixel sequence: " + view)
            for index, row in enumerate(rows):
                item = row.get("camera_sources", {}).get(view)
                if not isinstance(item, dict) or item.get("member") not in members:
                    raise ValueError("original camera frame join missing: " + view)
                data = archive.read(item["member"])
                if _sha(data) != item.get("sha256"):
                    raise ValueError("original camera pixel hash mismatch: " + view)
                with Image.open(io.BytesIO(data)) as frame:
                    frame.load()
                    if frame.format != "PNG" or frame.width <= 0 or frame.height <= 0:
                        raise ValueError("original camera pixel decode invalid: " + view)
                    if not seal.get("diagnostic_fixture") and frame.size != DIMENSIONS[view]:
                        raise ValueError("original camera dimensions mismatch: " + view)
        decoded[view] = len(members)
    return {"case_id": case_id, "site_packet_sha256": expected_site_sha256,
            "source_measurements": measured, "decoded_original_pixels": decoded,
            "diagnostic_fixture": bool(seal.get("diagnostic_fixture")),
            "physical_completion": "unreviewed", "legal_status": "unresolved_judgment"}
