"""CPU-only source and geometry checks for parking_measure.py."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("parking_measure.py")


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    native = root / "native.json"
    geometry_source = root / "roadway.json"
    trace = root / "pose-extract.json"
    geometry = root / "geometry.json"
    output = root / "observations.json"
    native_hash = write(native, {"frame_map": "diagnostic Native stand-in; no physical claim"})
    source_hash = write(geometry_source, {"road_edge": "diagnostic context; no physical claim"})
    pose = {
        "format": "worker-saved-pose-extract", "native_trace_path": str(native),
        "native_trace_sha256": native_hash,
        "frames": [
            {"frame": 0, "time_s": 0, "heading_deg": 0, "speed_mps": 0,
             "center_xy": [0, 0]},
            {"frame": 1, "time_s": 0.05, "heading_deg": 180, "speed_mps": 0,
             "center_xy": [0, 0]},
        ],
    }
    context = {
        "format": "worker-road-edge-context", "source_path": str(geometry_source),
        "source_sha256": source_hash, "roadway_class": "roadway",
        "road_edge_identified": True, "edge_tangent_xy": [1, 0],
        "lawful_traffic_direction_xy": [1, 0],
    }
    write(trace, pose)
    write(geometry, context)
    command = [sys.executable, str(SCRIPT), "--trace", str(trace),
               "--geometry", str(geometry), "--output", str(output)]
    passed = subprocess.run(command, text=True, capture_output=True)
    assert passed.returncode == 0, passed.stderr
    result = json.loads(output.read_text())
    rows = result["observations"]
    assert len(rows) == 2
    assert abs(rows[0]["edge_parallel_angle_deg"]) < 1e-8
    assert abs(rows[1]["edge_parallel_angle_deg"]) < 1e-8
    assert abs(rows[0]["lawful_traffic_heading_angle_deg"]) < 1e-8
    assert abs(rows[1]["lawful_traffic_heading_angle_deg"] - 180) < 1e-8
    print("positive saved pose geometry: passed")

    native.write_text("changed source\n")
    stale = subprocess.run(command, text=True, capture_output=True)
    assert stale.returncode != 0 and "Native trace hash mismatch" in stale.stderr
    print("negative stale Native source hash: rejected")
    native.write_text(json.dumps({"frame_map": "diagnostic Native stand-in; no physical claim"}, sort_keys=True) + "\n")

    context["road_edge_identified"] = False
    write(geometry, context)
    missing = subprocess.run(command, text=True, capture_output=True)
    assert missing.returncode != 0 and "roadway and edge must be identified" in missing.stderr
    print("negative unidentified roadway edge: rejected")

    context["road_edge_identified"] = True
    write(geometry, context)
    pose["frames"][1]["time_s"] = 0
    write(trace, pose)
    unordered = subprocess.run(command, text=True, capture_output=True)
    assert unordered.returncode != 0 and "not strictly ordered" in unordered.stderr
    print("negative unordered source frames: rejected")
