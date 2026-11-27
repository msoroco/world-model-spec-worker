"""Separate, explicitly synthetic CPU fixture admission for compatibility.

The diagnostic fixture retains source-hashed frame, ray and exception rows,
but its color videos are generated pixels and cannot establish visibility.
"""
from __future__ import annotations

import json
from pathlib import Path

from rail_native_capture import CAMERAS
from rail_saved_measurement import _source
from rail_sight_measurement import measure


def verify_diagnostic(root, receipt, packet, case_id):
    root = Path(root).resolve()
    if (receipt.get("capture_kind") != "diagnostic_fixture" or
            receipt.get("case_id") != case_id or
            (receipt.get("fps"), receipt.get("duration_s"), receipt.get("frame_count")) !=
            (20, 45, 900) or receipt.get("legal_conclusion") is not None):
        raise ValueError("synthetic rail fixture identity/profile differs")
    if packet.get("diagnostic_fixture") is not True or packet.get("case_id") != case_id:
        raise ValueError("synthetic rail packet identity differs")
    frames = json.loads(_source(root, receipt["frames"]).read_text())
    camera_map = json.loads(_source(root, receipt["camera_map"]).read_text())
    if (not isinstance(frames, list) or not isinstance(camera_map, list) or
            len(frames) != 900 or len(camera_map) != 900):
        raise ValueError("synthetic rail full-frame history required")
    for index, (row, cameras) in enumerate(zip(frames, camera_map)):
        if (row.get("original_frame") != index or
                cameras.get("original_frame") != index or
                set(cameras.get("sources", {})) != set(CAMERAS)):
            raise ValueError("synthetic rail frame/camera join differs")
    map_source = _source(root, packet["original_map_source"])
    observation = measure(root, packet, map_source.read_text(), frames)
    if receipt.get("measurement") != observation:
        raise ValueError("synthetic rail fixture measurement differs")
    return {"case_id": case_id, "source_complete": True,
            "original_frame_count": 900, "camera_views": list(CAMERAS),
            "observation": observation, "legal_conclusion": None,
            "diagnostic_fixture": True}
