"""Read-only audit of original saved sources for NRS 484B.223(3)(c).

This checks provenance and measurement arithmetic. It cannot establish a road's
legal status, camera visibility, physical motion, or statutory compliance.
"""

import hashlib
import importlib.util
import json
from math import isclose, isfinite
from pathlib import Path, PurePosixPath


_SPEC = importlib.util.spec_from_file_location(
    "center_lane_measurement_for_audit", Path(__file__).with_name("center_lane_measurement.py")
)
_MEASUREMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MEASUREMENT)
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _read_bound_json(root, binding):
    if not isinstance(binding, dict):
        raise ValueError("missing source binding")
    relative = binding.get("path")
    digest = binding.get("sha256")
    if not isinstance(relative, str) or not relative or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("incomplete source binding")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or relative.startswith("./"):
        raise ValueError("source path escapes attempt")
    source = (root / relative).resolve()
    if not source.is_relative_to(root.resolve()) or not source.is_file():
        raise ValueError("missing original source: " + relative)
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest.lower():
        raise ValueError("source hash mismatch: " + relative)
    return json.loads(raw.decode("utf-8"))


def audit_saved_delivery(attempt_root, receipt):
    """Recompute a delivered case from its hash-bound original saved trace.

    The attempt contains JSON for the Native body/lane trace, independent site
    review and lane-design sources, and a frame map. The receipt only names and
    hashes those files; it cannot replace them with its own values.
    """
    root = Path(attempt_root).resolve()
    if not receipt.get("case_id") or not receipt.get("attempt_id"):
        raise ValueError("missing case or attempt identity")
    trace = _read_bound_json(root, receipt.get("original_trace"))
    for field in ("highway_context_source", "lane_design_source"):
        source = trace.get(field)
        if source != receipt.get(field):
            raise ValueError("trace and receipt source binding differ: " + field)
        _read_bound_json(root, source)
    if trace.get("source") != {"path": receipt["original_trace"]["path"]}:
        raise ValueError("trace self-binding differs from original trace")
    # A file cannot contain its own SHA256. The original trace's self-reference
    # therefore records its path only; the receipt supplies the content hash.
    frame_map = _read_bound_json(root, receipt.get("frame_map_source"))
    if frame_map.get("fps") != 20:
        raise ValueError("original frame map must use 20 Hz")
    frames = [row.get("frame") for row in trace.get("samples", [])]
    mappings = frame_map.get("frames")
    if not isinstance(mappings, list) or [row.get("frame") for row in mappings] != frames:
        raise ValueError("original frame map does not join trace frames")
    for row in mappings:
        sources = row.get("camera_sources")
        if not isinstance(sources, dict) or set(sources) != set(VIEWS) or not all(sources.values()):
            raise ValueError("incomplete four-camera frame mapping")
    measured = _MEASUREMENT.measure_center_lane_distance(trace)
    delivered = receipt.get("delivered_measurement")
    if not isinstance(delivered, dict):
        raise ValueError("missing delivered measurement")
    for key in ("turn_frame", "merge_frame", "merge_observed", "censored", "boundary_ft"):
        if delivered.get(key) != measured[key]:
            raise ValueError("delivered event or boundary mismatch: " + key)
    for key in ("distance_m", "distance_ft"):
        value = delivered.get(key)
        if not isinstance(value, (int, float)) or not isfinite(value) or not isclose(value, measured[key], rel_tol=0, abs_tol=1e-6):
            raise ValueError("delivered distance mismatch: " + key)
    return {"case_id": receipt["case_id"], "attempt_id": receipt["attempt_id"],
            "original_trace_sha256": receipt["original_trace"]["sha256"],
            "frame_map_sha256": receipt["frame_map_source"]["sha256"],
            "verified_frame_count": len(frames), "measured": measured,
            "physical_acceptance": None, "legal_judgment": None}
