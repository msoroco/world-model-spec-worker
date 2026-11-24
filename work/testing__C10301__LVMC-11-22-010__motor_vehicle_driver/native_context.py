"""Source-bound original context acquisition for the alley observation cases.

The local Native adapter must supply measured body and marking polygons from the
same world frame. A draft worker polygon is deliberately insufficient.
"""
from __future__ import annotations

import hashlib
import json
import math


def _polygon(points, name):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(name + " polygon needs three vertices")
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in point
        ):
            raise ValueError(name + " polygon has nonfinite vertex")
    turns = []
    for a, b, c in zip(points, points[1:] + points[:1],
                       points[2:] + points[:2]):
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-9:
            turns.append(cross)
    if not turns or min(turns) < 0 < max(turns):
        raise ValueError(name + " polygon must be convex and nondegenerate")
    return points


def _axes(poly):
    for a, b in zip(poly, poly[1:] + poly[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) + abs(dy) <= 1e-9:
            raise ValueError("degenerate polygon edge")
        yield (-dy, dx)


def intersects(poly_a, poly_b):
    """Convex-polygon overlap, with touching counted as overlap."""
    a = _polygon(poly_a, "body")
    b = _polygon(poly_b, "marking")
    for nx, ny in list(_axes(a)) + list(_axes(b)):
        pa = [x * nx + y * ny for x, y in a]
        pb = [x * nx + y * ny for x, y in b]
        if max(pa) < min(pb) - 1e-9 or max(pb) < min(pa) - 1e-9:
            return False
    return True


def sample_context(case_id, native_frame, native_time_s, observed):
    """Validate separately acquired Native/map readbacks and seal one frame.

    `observed` is returned by the local scene adapter after the same world tick.
    Each static feature must have a reviewed source hash and a Native verification
    readback; this function never substitutes the worker geometry candidate.
    """
    if not case_id or type(native_frame) is not int or native_frame < 0:
        raise ValueError("exact case and original Native frame required")
    if type(native_time_s) not in (int, float) or not math.isfinite(native_time_s):
        raise ValueError("original Native time required")
    if not isinstance(observed, dict) or observed.get("native_frame") != native_frame:
        raise ValueError("context must match original Native frame")
    if abs(observed.get("native_time_s", math.inf) - native_time_s) > 0.001:
        raise ValueError("context must match original Native time")
    for key in ("map_sha256", "marking_source_sha256", "parking_source_sha256",
                "jurisdiction_source_sha256"):
        digest = observed.get(key)
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise ValueError("reviewed source hash required: " + key)
    if observed.get("marking_native_verified") is not True:
        raise ValueError("Native marking readback required")
    if observed.get("parking_native_verified") is not True:
        raise ValueError("Native parking designation readback required")
    body = _polygon(observed.get("body_footprint_xy_m"), "body")
    markings = observed.get("marking_polygons_xy_m")
    if not isinstance(markings, list) or not markings:
        raise ValueError("original marking polygons required")
    overlap = any(intersects(body, polygon) for polygon in markings)
    ttc = observed.get("time_to_conflict_s")
    if ttc is not None and (type(ttc) not in (int, float) or not math.isfinite(ttc) or ttc < 0):
        raise ValueError("invalid original time to conflict")
    signal = observed.get("traffic_signal")
    if signal not in ("none", "red", "amber", "green", "unknown"):
        raise ValueError("original signal readback required")
    if observed.get("signal_native_verified") is not True:
        raise ValueError("Native signal readback required")
    canonical = json.dumps(observed, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {
        "source_kind": "original_native_context_state", "case_id": case_id,
        "native_frame": native_frame, "native_time_s": native_time_s,
        "source_sha256": hashlib.sha256(canonical).hexdigest(),
        "straddles_marking": overlap,
        "time_to_conflict_s": ttc, "traffic_signal": signal,
        "map_sha256": observed["map_sha256"],
        "marking_source_sha256": observed["marking_source_sha256"],
        "parking_source_sha256": observed["parking_source_sha256"],
        "jurisdiction_source_sha256": observed["jurisdiction_source_sha256"],
    }


def sample_from_native(actor, world, snapshot, case_id, reviewed_site,
                       marking_reader, parking_reader, signal_reader,
                       conflict_reader):
    """Acquire one same-tick Native context with explicit site adapters.

    Readers query the actual loaded map or scene and return original readbacks.
    They cannot be replaced by a worker-draft access-aisle rectangle. The caller
    owns synchronization, resource cleanup, and persistence of raw readbacks.
    """
    frame = int(snapshot.frame)
    time_s = float(snapshot.timestamp.elapsed_seconds)
    if world.get_map().name != reviewed_site.get("map_name"):
        raise ValueError("Native map differs from reviewed site")
    for key in ("map_sha256", "jurisdiction_source_sha256"):
        if key not in reviewed_site:
            raise ValueError("reviewed site source missing: " + key)
    transform = actor.get_transform()
    location = transform.location
    yaw = math.radians(float(transform.rotation.yaw))
    extent = actor.bounding_box.extent
    half_length, half_width = float(extent.x), float(extent.y)
    if min(half_length, half_width) <= 0 or not all(map(math.isfinite,
            (location.x, location.y, yaw, half_length, half_width))):
        raise ValueError("valid Native body extent and pose required")
    cosine, sine = math.cos(yaw), math.sin(yaw)
    body = []
    for dx, dy in [(-half_length, -half_width), (half_length, -half_width),
                   (half_length, half_width), (-half_length, half_width)]:
        body.append([float(location.x + dx * cosine - dy * sine),
                     float(location.y + dx * sine + dy * cosine)])
    markings = marking_reader(world, frame)
    parking = parking_reader(world, frame)
    signal = signal_reader(actor, world, frame)
    conflict = conflict_reader(actor, world, frame)
    for name, packet in (("marking", markings), ("parking", parking),
                         ("signal", signal), ("conflict", conflict)):
        if not isinstance(packet, dict) or packet.get("native_frame") != frame:
            raise ValueError(name + " original Native readback frame mismatch")
    if conflict.get("native_verified") is not True:
        raise ValueError("Native conflict readback required")
    observed = {
        "native_frame": frame, "native_time_s": time_s,
        "map_sha256": reviewed_site["map_sha256"],
        "jurisdiction_source_sha256": reviewed_site["jurisdiction_source_sha256"],
        "marking_source_sha256": markings.get("source_sha256"),
        "parking_source_sha256": parking.get("source_sha256"),
        "marking_native_verified": markings.get("native_verified"),
        "parking_native_verified": parking.get("native_verified"),
        "marking_polygons_xy_m": markings.get("polygons_xy_m"),
        "body_footprint_xy_m": body,
        "traffic_signal": signal.get("state"),
        "signal_native_verified": signal.get("native_verified"),
        "time_to_conflict_s": conflict.get("time_to_conflict_s"),
    }
    return sample_context(case_id, frame, time_s, observed)
