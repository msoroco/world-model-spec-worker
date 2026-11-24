"""Source-bound distance of a vehicle footprint to the nearest surveyed rail.

This module measures geometry and rest state; it never decides legal compliance.
The caller must acquire rail geometry, vehicle pose/extent and stop reason from
Native sources. It does not accept a precomputed distance channel.
"""
import json
import math
from pathlib import Path


FEET_50_M = 15.24


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("point must contain x and y")
    out = (float(value[0]), float(value[1]))
    if not all(math.isfinite(v) for v in out):
        raise ValueError("nonfinite geometry")
    return out


def _orient(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _intersects(a, b, c, d):
    ab1, ab2 = _orient(a,b,c), _orient(a,b,d)
    cd1, cd2 = _orient(c,d,a), _orient(c,d,b)
    if not (ab1*ab2 <= 0 and cd1*cd2 <= 0):
        return False
    if ab1 == ab2 == cd1 == cd2 == 0:
        return (max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0]))
                and max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1])))
    return True


def _point_segment(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    den = dx*dx+dy*dy
    if den == 0:
        raise ValueError("zero-length segment")
    t = max(0.0, min(1.0, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def _segment_distance(a,b,c,d):
    if _intersects(a,b,c,d):
        return 0.0
    return min(_point_segment(a,c,d),_point_segment(b,c,d),
               _point_segment(c,a,b),_point_segment(d,a,b))


def measure(packet):
    """Return per-frame nearest rail distance and source-backed rest timeline."""
    if packet.get("format") != "rail-footprint-native-source-v1":
        raise ValueError("wrong source packet format")
    rails = packet.get("rails")
    if not isinstance(rails, list) or len(rails) < 2:
        raise ValueError("both physical rails required")
    parsed = []
    seen = set()
    for rail in rails:
        rid = rail.get("rail_id")
        if not isinstance(rid, str) or not rid or rid in seen:
            raise ValueError("unique rail IDs required")
        seen.add(rid)
        if rail.get("source_kind") not in ("map_survey", "native_survey") or not rail.get("source_ref"):
            raise ValueError("rail survey source required")
        points = [_point(x) for x in rail.get("polyline_xy_m", [])]
        if len(points) < 2:
            raise ValueError("rail polyline required")
        parsed.extend((rid,points[i],points[i+1]) for i in range(len(points)-1))
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 600:
        raise ValueError("600 frames at 20 Hz required")
    out = []
    for i, frame in enumerate(frames):
        if frame.get("frame") != i or abs(float(frame.get("sim_time_s", -1))-i/20) > 1e-6:
            raise ValueError("frame map or cadence mismatch")
        if not frame.get("pose_source_ref") or not frame.get("extent_source_ref") or not frame.get("speed_source_ref"):
            raise ValueError("Native pose, extent and speed sources required")
        poly = [_point(x) for x in frame.get("vehicle_footprint_xy_m", [])]
        if len(poly) != 4:
            raise ValueError("four vehicle footprint corners required")
        speed = float(frame.get("speed_mps", -1))
        if not math.isfinite(speed) or speed < 0:
            raise ValueError("invalid speed")
        distances = [(rid, _segment_distance(poly[j],poly[(j+1)%4],a,b))
                     for rid,a,b in parsed for j in range(4)]
        rid, distance = min(distances, key=lambda item:item[1])
        reason = frame.get("halt_reason")
        if reason not in ("voluntary", "traffic_conflict", "law", "officer", "traffic_device", "unknown"):
            raise ValueError("halt reason must be sourced or unknown")
        if reason != "unknown" and not frame.get("halt_reason_source_ref"):
            raise ValueError("halt reason source required")
        out.append({"frame":i,"sim_time_s":i/20,"nearest_rail_id":rid,
                    "footprint_to_nearest_rail_m":round(distance,6),
                    "inside_50ft_band":distance < FEET_50_M,
                    "at_rest":speed <= 0.05,"halt_reason":reason})
    return {"format":"rail-footprint-measurement-v1","threshold_m":FEET_50_M,
            "source_packet_sha256":__import__("hashlib").sha256(json.dumps(packet,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "frames":out}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: rail_footprint_meter.py source.json output.json")
    result=measure(json.loads(Path(sys.argv[1]).read_text()))
    Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+"\n")
