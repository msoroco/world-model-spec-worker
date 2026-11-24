"""Check whether the pinned public fixture can return a complete long trace."""
import hashlib
import json
from pathlib import Path

from worker_exchange import fixture_generator


ROOT = Path(__file__).resolve().parents[2]
LIMIT = 2 * 1024 * 1024
COUNTS = (36120, 36121, 36122)


def compact_trace_size(count):
    size = 0
    for frame in range(count):
        row = {
            "frame": frame,
            "time_s": frame / 20,
            "position": {"x": 0, "y": 0, "z": 0},
            "heading_deg": 0,
            "speed_mps": 0,
        }
        size += len(json.dumps(row, separators=(",", ":")).encode()) + 1
    return size


def zero_based_trace_size_floor(count):
    """Size with zero-based frame values and every other number one digit."""
    return sum(len(f'{{"frame":{frame},"time_s":0,"position":'
                   f'{{"x":0,"y":0,"z":0}},"heading_deg":0,"speed_mps":0}}\n')
               for frame in range(count))


def rejected(spec):
    try:
        fixture_generator.inspect(spec)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("Unexpected fixture generator acceptance")


def main():
    minimum_valid_shape = {
        str(count): compact_trace_size(count) for count in COUNTS
    }
    zero_based_floor = {
        str(count): zero_based_trace_size_floor(count) for count in COUNTS
    }
    one_digit_floor = {str(count): count * len(
        '{"frame":0,"time_s":0,"position":{"x":0,"y":0,"z":0},"heading_deg":0,"speed_mps":0}\n') - 1
        for count in COUNTS}
    assert all(size > LIMIT for size in minimum_valid_shape.values())
    assert all(size > LIMIT for size in one_digit_floor.values())
    baseline = {"files": {}, "graphs": [], "videos": []}
    graph = dict(baseline)
    graph["graphs"] = [{"path": "trace.jsonl", "attributes": {},
                        "nodes": [], "edges": []}]
    video = dict(baseline)
    video["videos"] = [{"path": "overview.mkv", "frames": 36120,
                        "width": 1920, "height": 1080, "fps": 20,
                        "color": "black"}]
    graph_error = rejected(graph)
    video_error = rejected(video)
    assert "adapter JSON" in graph_error
    assert "bounded diagnostic" in video_error
    direct = ROOT / ".runtime-work/owner150142/current-runner-tour-bus-below-primary-direct-v1/positive/trace.jsonl"
    source = {"path": str(direct.relative_to(ROOT)), "sha256": hashlib.sha256(direct.read_bytes()).hexdigest(),
              "bytes": direct.stat().st_size, "rows": sum(1 for _ in direct.open())}
    assert source["rows"] == 36120
    assert source["bytes"] > LIMIT
    print(json.dumps({"format": "c150142-current-long-fixture-representation-probe-v1",
                      "returned_file_cap_bytes": LIMIT,
                      "one_digit_per_numeric_field_floor_bytes": one_digit_floor,
                      "zero_based_frame_size_floor_bytes": zero_based_floor,
                      "valid_trace_shape_bytes": minimum_valid_shape,
                      "direct_trace": source,
                      "graph_trace_rejection": graph_error,
                      "long_generated_video_rejection": video_error,
                      "official_long_compatibility_passed": False}, indent=2))


if __name__ == "__main__":
    main()
