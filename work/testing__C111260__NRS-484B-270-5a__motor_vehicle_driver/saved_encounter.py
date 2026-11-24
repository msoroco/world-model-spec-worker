"""Independent saved-source join for the six NRS 484B.270(5)(a) cases.

This measures original Native history; it does not decide due care or verify pixels.
"""

import hashlib
import importlib.util
import json
from pathlib import Path


ASSIGNMENT = "testing__C111260__NRS-484B-270-5a__motor_vehicle_driver"
CAMERAS = ("front", "rear", "left", "right")
KINDS = ("bicycle", "electric_bicycle", "electric_scooter")
RESPONSES = ("brake", "maintain")
SPEC = importlib.util.spec_from_file_location("cyclist_encounter", Path(__file__).with_name("cyclist_encounter.py"))
ENCOUNTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENCOUNTER)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_source(root, reference):
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("source path and SHA256 required")
    rel = Path(reference["path"])
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("source path escapes attempt")
    path = root / rel
    if not path.is_file() or path.is_symlink() or path.resolve().parent != root.resolve():
        raise ValueError("original source missing or outside attempt")
    if _sha(path) != reference["sha256"]:
        raise ValueError("original source hash drift")
    return json.loads(path.read_text(encoding="utf-8"))


def _target(case_id):
    prefix = ASSIGNMENT + "__"
    if not isinstance(case_id, str) or not case_id.startswith(prefix):
        raise ValueError("foreign exact case")
    suffix = case_id[len(prefix):]
    for kind in KINDS:
        for response in RESPONSES:
            if suffix == kind + "_" + response:
                return kind, response
    raise ValueError("unknown exact case")


def finalize_saved(attempt):
    """Read an attempt packet and return source-bound observations only.

    The packet contains the exact case, original map, history and camera-frame
    map references. Each reference is SHA-bound and confined to the attempt.
    """
    root = Path(attempt).resolve()
    if not root.is_dir():
        raise ValueError("attempt directory missing")
    packet_path = root / "encounter-packet.json"
    if not packet_path.is_file() or packet_path.is_symlink():
        raise ValueError("encounter packet missing")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    kind, response = _target(packet.get("case_id"))
    if packet.get("source") != "original_native" or packet.get("hz") != 20:
        raise ValueError("original 20 Hz acquisition required")
    map_packet = _load_source(root, packet.get("site"))
    site = ENCOUNTER.validate_site(map_packet, kind)
    rows = _load_source(root, packet.get("history"))
    if not isinstance(rows, list) or len(rows) != 900:
        raise ValueError("900 original encounter frames required")
    for row in rows:
        if row.get("case_id") != packet["case_id"]:
            raise ValueError("original history case drift")
    measurement = ENCOUNTER.audit_original_history(rows,
        expected_rider_kind=kind, expected_response=response,
        map_sha256=site["map_sha256"],
        expected_person_actor_id=map_packet["rider"]["person_actor_id"])
    camera_frames = _load_source(root, packet.get("camera_frames"))
    original_frames = [row["frame"] for row in rows]
    if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
        raise ValueError("four camera frame maps required")
    for camera in CAMERAS:
        stream = camera_frames[camera]
        if not isinstance(stream, list) or len(stream) != 900:
            raise ValueError("camera frame count incomplete: " + camera)
        if stream != original_frames:
            raise ValueError("camera frame identity mismatch: " + camera)
    return {
        "format": "worker-saved-encounter-observation",
        "case_id": packet["case_id"],
        "kind": kind,
        "response": response,
        "map_sha256": site["map_sha256"],
        "rider_person_actor_id": map_packet["rider"]["person_actor_id"],
        "source_hashes": {name: packet[name]["sha256"] for name in ("site", "history", "camera_frames")},
        "original_frames": len(rows),
        "camera_frames": {name: len(camera_frames[name]) for name in CAMERAS},
        "measurement": measurement,
        "full_video_decode": False,
        "actual_pixels": False,
        "physical_completion": False,
        "legal_judgment": "unresolved",
    }
