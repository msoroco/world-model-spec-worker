"""Independent saved-source and four-camera audit for C157964 attempts."""

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from native_capture import VIEWS
from reviewed_site import SITE_ROLES
from yield_view import measure_original, require


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _read_json(path):
    return json.loads(path.read_text())


def _contained(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            "saved source path invalid")
    target = (root / relative).resolve()
    require(target.is_relative_to(root.resolve()) and target.is_file(),
            "saved source path escapes or is missing")
    return target


def audit_saved(attempt, case, *, allow_diagnostic=False,
                expected_site_packet_sha256=None):
    """Reopen all copied source bytes and 3,600 camera packets.

    Success is a CPU source-integrity result. It does not assert physical
    visibility, realized right-of-way, legal hazard or canonical acceptance.
    """
    root = Path(attempt).resolve()
    seal = _read_json(root / "seal.json")
    require(seal.get("format") == "c157964-native-attempt-v1" and
            seal.get("case_id") == case.case_id and
            seal.get("frame_count") == 900 and seal.get("fps") == 20 and
            seal.get("views") == list(VIEWS), "Native attempt seal differs")
    require(allow_diagnostic or seal.get("diagnostic_fixture") is False,
            "diagnostic attempt cannot be original delivery")
    require(allow_diagnostic or expected_site_packet_sha256,
            "independent reviewed site hash missing")
    packet_bytes = (root / "reviewed-site-packet.json").read_bytes()
    require(_sha(packet_bytes) == seal.get("site_packet_sha256"),
            "reviewed site packet changed")
    if expected_site_packet_sha256 is not None:
        require(_sha(packet_bytes) == expected_site_packet_sha256,
                "independent reviewed site hash differs")
    packet = json.loads(packet_bytes)
    require(packet.get("format") == "c157964-reviewed-yield-site-v1" and
            packet.get("case_id") == case.case_id and
            packet.get("provenance") == "reviewed_original",
            "reviewed site identity differs")
    site = packet["site"]
    source_index_path = root / "reviewed-source-index.json"
    require(_sha(source_index_path.read_bytes()) == seal.get("reviewed_source_index_sha256"),
            "reviewed source index changed")
    sources = _read_json(source_index_path)
    require(set(sources) == set(SITE_ROLES) and
            set(packet["sources"]) == set(SITE_ROLES),
            "reviewed source roles differ")
    for role in SITE_ROLES:
        copy_ref, original_ref = sources[role], packet["sources"][role]
        copied = _contained(root, copy_ref["path"])
        require(_sha(copied.read_bytes()) == copy_ref.get("sha256") ==
                original_ref.get("sha256") == site.get(role + "_source_sha256"),
                "reviewed source bytes changed: " + role)
    rows_path = root / "rows.json"
    measurement_path = root / "measurement.json"
    index_path = root / "camera-index.json"
    for path, key in ((rows_path, "rows_sha256"),
                      (measurement_path, "measurement_sha256"),
                      (index_path, "camera_index_sha256")):
        require(_sha(path.read_bytes()) == seal.get(key), "sealed saved bytes changed: " + key)
    rows = _read_json(rows_path)
    measured = measure_original(rows, site, case)
    require(measured == _read_json(measurement_path), "saved measurement differs")
    cameras = _read_json(index_path)
    require(set(cameras) == set(VIEWS), "four saved camera views missing")
    total = 0
    for view in VIEWS:
        entries = cameras[view]
        require(isinstance(entries, list) and len(entries) == 900,
                "saved camera frame count differs")
        sensor_id = None
        for row, entry in zip(rows, entries):
            require(entry.get("frame") == row["original_frame"] and
                    abs(entry.get("time_s", -1) - row["time_s"]) <= .005,
                    "saved camera frame/time join differs")
            sensor_id = sensor_id or entry.get("sensor_id")
            require(sensor_id and entry.get("sensor_id") == sensor_id,
                    "saved camera sensor identity changed")
            payload = _contained(root, entry.get("path")).read_bytes()
            require(_sha(payload) == entry.get("sha256"),
                    "saved camera bytes changed")
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                require(list(image.size) == site["camera_dimensions"][view],
                        "saved camera dimensions differ")
            total += 1
    return {"format": "c157964-saved-source-audit-v1", "case_id": case.case_id,
            "diagnostic_fixture": seal["diagnostic_fixture"],
            "native_seal_sha256": _sha((root / "seal.json").read_bytes()),
            "frame_count": 900, "decoded_camera_frames": total,
            "source_integrity": True, "physical_completion": "unverified",
            "legal_judgment": None}
