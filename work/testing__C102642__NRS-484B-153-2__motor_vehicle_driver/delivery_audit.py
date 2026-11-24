"""Independent saved-source audit for a Native door interaction attempt."""
from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path

from PIL import Image

from delivery_measure import measure, read_sealed_trace
from native_capture import CAMERAS, FRAME_COUNT


def audit_saved(attempt: Path, *, trace_sha256: str, case_id: str,
                act: str, side: str, expected_dimensions: dict) -> dict:
    """Decode all original camera PNGs and remeasure the sealed actor trace.

    Expected dimensions are explicit per view because a diagnostic fixture can
    be small. A production attempt must supply the actual capture profile.
    """
    if set(expected_dimensions) != set(CAMERAS):
        raise ValueError("four expected camera dimensions are required")
    trace = read_sealed_trace(attempt / "native-trace.json", trace_sha256)
    frames = trace.get("frames")
    if not isinstance(frames, list) or len(frames) != FRAME_COUNT:
        raise ValueError("full 900-frame original trace is required")
    measurement = measure(trace, expected_case_id=case_id,
                          expected_act=act, expected_side=side)
    expected = set()
    for frame in frames:
        frame_id = frame["frame_id"]
        for view in CAMERAS:
            location = attempt / "cameras" / view / f"{frame_id:06d}.png"
            expected.add(location)
            data = location.read_bytes()
            if hashlib.sha256(data).hexdigest() != frame.get("camera_sha256", {}).get(view):
                raise ValueError("camera bytes differ from sealed original trace: " + view)
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG" or image.size != tuple(expected_dimensions[view]):
                    raise ValueError("camera format or dimensions changed: " + view)
                image.load()
    observed = set((attempt / "cameras").rglob("*.png"))
    if observed != expected:
        raise ValueError("camera frame inventory differs from original trace")
    return {"case_id": case_id, "original_trace_sha256": trace_sha256,
            "frame_count": FRAME_COUNT, "decoded_camera_frames": len(expected),
            "act_on_closest_side": measurement["act_on_closest_side"],
            "minimum_body_gap_m": measurement["minimum_body_gap_m"],
            "legal_interference": "unresolved_judgment",
            "physical_visibility": "requires_human_review"}
