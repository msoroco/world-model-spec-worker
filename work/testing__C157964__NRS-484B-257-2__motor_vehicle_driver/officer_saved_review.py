"""Bind independent original-frame review to Native subsection 2 sources.

Programmed poses are retained as construction facts. Only a separately
supplied, capture-bound review may populate observed officer direction and
traffic control for the saved measurement analyzer.
"""

import hashlib
import json
from pathlib import Path

from officer_source_intake import load_and_validate
from officer_yield_exception import analyze


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _output_root(path):
    path = Path(path).resolve()
    repo = Path(__file__).resolve().parents[2]
    if path.is_relative_to(repo) and not path.is_relative_to(repo / ".runtime-work"):
        raise ValueError("Saved review sources must stay under .runtime-work")
    return path


def process(capture_path, review_path, source_root, source_packet, output_root,
            *, native_map_id, intersection_id):
    capture_path, review_path = Path(capture_path), Path(review_path)
    capture = json.loads(capture_path.read_text())
    review = json.loads(review_path.read_text())
    intake = load_and_validate(source_root, source_packet)
    if (capture.get("format") != "worker-officer-subsection-2-native-capture" or
            capture.get("site_id") != intake["site_id"] or
            capture.get("source_packet_sha256") != _sha(source_packet)):
        raise ValueError("Native capture and reviewed site source differ")
    rows = capture.get("rows")
    if not isinstance(rows, list) or len(rows) < 3 or len(rows) != capture.get("frame_count"):
        raise ValueError("Incomplete Native capture for saved review")
    if (review.get("format") != "worker-officer-subsection-2-original-frame-review" or
            review.get("case_id") != capture.get("case_id") or
            review.get("site_id") != intake["site_id"] or
            review.get("capture_sha256") != _sha(capture_path) or
            review.get("source_packet_sha256") != _sha(source_packet) or
            not isinstance(review.get("reviewer"), str) or not review["reviewer"]):
        raise ValueError("Independent original-frame review binding missing")
    observed = review.get("frames")
    if not isinstance(observed, list) or len(observed) != len(rows):
        raise ValueError("Incomplete original-frame review")
    if not isinstance(native_map_id, str) or not native_map_id or type(intersection_id) is not int:
        raise ValueError("Native map and intersection identity required")
    first = rows[0]["native_actor_source"]
    officer_id = first.get("officer_actor_id")
    if type(officer_id) is not int:
        raise ValueError("Original officer actor identity required")
    source_paths = intake["source_paths"]
    site = json.loads(Path(source_packet).read_text())["review"]
    entrances = {item["entrance_id"]: item for item in site["entrances"]}
    context = {"native_map_id": native_map_id, "intersection_id": intersection_id,
               "officer_actor_id": officer_id,
               "authority_source": source_paths["officer_authority"],
               "uniform_video_source": None,
               "direction_video_source": None,
               "junction_source": source_paths["road"],
               "ego_route_source": source_paths["road"],
               "sign_inventory_source": source_paths["sign_inventory"],
               "other_entrance_source": source_paths["sign_inventory"],
               "highway_status_source": source_paths["road"],
               "non_through_highway": True,
               "ego_entrance_device": entrances[intake["ego_entrance_id"]]["device"],
               "other_entrance_device": entrances[intake["other_entrance_id"]]["device"],
               "intersection_polygon_xy_m": intake["intersection_polygon_xy_m"]}
    history, frame_map = [], []
    for index, (row, observation) in enumerate(zip(rows, observed)):
        source = row.get("native_actor_source")
        if not isinstance(source, dict) or source.get("frame") != row.get("carla_frame"):
            raise ValueError("Native source and capture frame differ")
        refs = source.get("camera_raw_sources")
        if not isinstance(refs, dict) or set(refs) != {"overview", "approach", "reference_corner", "driver_reference"}:
            raise ValueError("Four original camera sources required")
        if (not isinstance(observation, dict) or
                observation.get("carla_frame") != source["frame"] or
                observation.get("officer_actor_id") != officer_id or
                observation.get("direction_frame_source") not in refs.values() or
                observation.get("uniform_frame_source") not in refs.values() or
                observation.get("control_frame_source") not in refs.values() or
                observation.get("officer_direction_observed") not in ("stop", "go", "unclear") or
                type(observation.get("traffic_control_observed")) is not bool):
            raise ValueError("Original-frame officer review differs from Native sources")
        if source.get("officer_actor_id") != officer_id:
            raise ValueError("Officer actor identity changed")
        ego, other = source.get("ego"), source.get("other")
        if not isinstance(ego, dict) or not isinstance(other, dict):
            raise ValueError("Native ego and other body sources required")
        history.append({"frame": source["frame"], "time_s": source["time_s"],
                        "officer_actor_id": officer_id,
                        "officer_direction_observed": observation["officer_direction_observed"],
                        "direction_frame_source": observation["direction_frame_source"],
                        "traffic_control_observed": observation["traffic_control_observed"],
                        "ego": {"speed_mps": ego["speed_mps"],
                                "body_vertices_xy_m": ego["body_vertices_xy_m"]},
                        "other_body_vertices_xy_m": other["body_vertices_xy_m"]})
        frame_map.append({"video_frame": index, "carla_frame": source["frame"],
                          "time_s": source["time_s"]})
    context["uniform_video_source"] = observed[0]["uniform_frame_source"]
    context["direction_video_source"] = observed[0]["direction_frame_source"]
    output_root = _output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    for name, payload in (("officer_context.json", json.dumps(context, sort_keys=True) + "\n"),
                          ("officer_history.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in history)),
                          ("video_frames.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_map))):
        path = output_root / name
        if path.exists():
            raise ValueError("Saved source already exists: " + name)
        path.write_text(payload)
    result = analyze(output_root)
    result["capture_sha256"] = _sha(capture_path)
    result["review_sha256"] = _sha(review_path)
    result["source_packet_sha256"] = _sha(source_packet)
    return result
