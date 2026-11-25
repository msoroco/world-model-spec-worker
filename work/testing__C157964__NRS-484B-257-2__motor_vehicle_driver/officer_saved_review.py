"""Bind independent original-frame review to Native subsection 2 sources.

Programmed poses are retained as construction facts. Only a separately
supplied, capture-bound review may populate observed officer direction and
traffic control for the saved measurement analyzer.
"""

import hashlib
import json
from pathlib import Path
import subprocess

from officer_source_intake import load_and_validate
from officer_yield_exception import analyze
from officer_direction import PREFIX


EXPECTED = {PREFIX + "officer_controls_go": (True, "go"),
            PREFIX + "officer_controls_hold": (True, "stop"),
            PREFIX + "officer_present_inactive": (False, "none")}
EXPECTED.update({f"{PREFIX}c157964_sub2_judgment_{judgment}-{rank:04d}": (True, "go")
                 for judgment in (1, 2, 3, 4, 5, 6)
                 for rank in range(2 if judgment == 4 else 3)})


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _output_root(path):
    path = Path(path).resolve()
    roots = [parent for parent in Path(__file__).resolve().parents
             if (parent / ".runtime-work").is_dir()]
    repo = roots[-1] if roots else None
    if repo is not None and path.is_relative_to(repo) and not path.is_relative_to(repo / ".runtime-work"):
        raise ValueError("Saved review sources must stay under .runtime-work")
    return path


def _camera_path(capture_path, reference, index):
    if not isinstance(reference, str) or not reference.endswith("#frame-" + str(index)):
        raise ValueError("Original camera video frame index differs")
    video = Path(reference.rsplit("#frame-", 1)[0])
    if not video.is_absolute():
        video = capture_path.parent / video
    video = video.resolve()
    if not video.is_relative_to(capture_path.parent.resolve()) or not video.is_file():
        raise ValueError("Original camera video source missing from attempt")
    return video


def _probe_camera(path, expected_frames):
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            streams[0].get("nb_read_frames") != str(expected_frames)):
        raise ValueError("Original camera video decode or frame count differs")


def process(capture_path, review_path, source_root, source_packet, output_root,
            *, native_map_id, intersection_id):
    capture_path, review_path = Path(capture_path), Path(review_path)
    capture = json.loads(capture_path.read_text())
    review = json.loads(review_path.read_text())
    intake = load_and_validate(source_root, source_packet)
    if (capture.get("format") != "worker-officer-subsection-2-native-capture" or
            capture.get("site_id") != intake["site_id"] or
            capture.get("source_packet_sha256") != _sha(source_packet) or
            capture.get("case_id") not in EXPECTED):
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
    camera_hashes = review.get("camera_sha256")
    camera_names = {"overview", "approach", "reference_corner", "driver_reference"}
    if not isinstance(camera_hashes, dict) or set(camera_hashes) != camera_names:
        raise ValueError("Four original camera hashes required")
    video_paths = {}
    first = rows[0]["native_actor_source"]
    officer_id = first.get("officer_actor_id")
    if type(officer_id) is not int:
        raise ValueError("Original officer actor identity required")
    source_paths = intake["source_paths"]
    site = json.loads(Path(source_packet).read_text())["review"]
    entrances = {item["entrance_id"]: item for item in site["entrances"]}
    context = {"native_map_id": native_map_id, "intersection_id": intersection_id,
               "case_id": capture["case_id"],
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
        if not isinstance(refs, dict) or set(refs) != camera_names:
            raise ValueError("Four original camera sources required")
        for name in camera_names:
            video = _camera_path(capture_path, refs[name], index)
            if name in video_paths and video_paths[name] != video:
                raise ValueError("Original camera source changed within capture")
            video_paths[name] = video
        if (not isinstance(observation, dict) or
                observation.get("carla_frame") != source["frame"] or
                observation.get("officer_actor_id") != officer_id or
                observation.get("direction_frame_source") not in refs.values() or
                observation.get("uniform_frame_source") not in refs.values() or
                observation.get("control_frame_source") not in refs.values() or
                observation.get("other_frame_source") not in refs.values() or
                observation.get("officer_direction_observed") not in ("stop", "go", "unclear", "none") or
                type(observation.get("traffic_control_observed")) is not bool or
                type(observation.get("other_approaching_observed")) is not bool):
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
                        "other_frame_source": observation["other_frame_source"],
                        "other_approaching_observed": observation["other_approaching_observed"],
                        "ego": {"speed_mps": ego["speed_mps"],
                                "body_vertices_xy_m": ego["body_vertices_xy_m"]},
                        "other_body_vertices_xy_m": other["body_vertices_xy_m"]})
        frame_map.append({"video_frame": index, "carla_frame": source["frame"],
                          "time_s": source["time_s"]})
    for name, path in video_paths.items():
        if _sha(path) != camera_hashes[name]:
            raise ValueError("Original camera bytes differ: " + name)
        _probe_camera(path, len(rows))
    context["uniform_video_source"] = observed[0]["uniform_frame_source"]
    context["direction_video_source"] = observed[0]["direction_frame_source"]
    output_root = _output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    existing_map = output_root / "video_frames.jsonl"
    if existing_map.exists():
        original_map = [json.loads(line) for line in existing_map.read_text().splitlines() if line.strip()]
        if len(original_map) != len(frame_map) or any(
                any(original.get(key) != expected[key] for key in ("video_frame", "carla_frame", "time_s"))
                for original, expected in zip(original_map, frame_map)):
            raise ValueError("Capture-time original frame map differs from saved review")
    else:
        existing_map.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_map))
    for name, payload in (("officer_context.json", json.dumps(context, sort_keys=True) + "\n"),
                          ("officer_history.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in history))):
        path = output_root / name
        if path.exists():
            raise ValueError("Saved source already exists: " + name)
        path.write_text(payload)
    result = analyze(output_root)
    result["capture_sha256"] = _sha(capture_path)
    result["review_sha256"] = _sha(review_path)
    result["source_packet_sha256"] = _sha(source_packet)
    expected_control, expected_direction = EXPECTED[capture["case_id"]]
    entry = result["first_ego_entry"] or result.get("first_hold_observation")
    result["case_id"] = capture["case_id"]
    result["target_checks"] = [
        {"target": "officer_control_observed_at_ego_entry",
         "requested": expected_control,
         "measured": entry["traffic_control_observed"],
         "matched": entry["traffic_control_observed"] is expected_control,
         "physical_cause_confirmed": False},
        {"target": "officer_direction_observed_at_ego_entry",
         "requested": expected_direction,
         "measured": entry["officer_direction_observed"],
         "matched": entry["officer_direction_observed"] == expected_direction,
         "physical_cause_confirmed": False}]
    if capture["case_id"] == PREFIX + "officer_controls_hold":
        held = result["first_ego_entry"] is None
        result["target_checks"].append({
            "target": "ego_held_outside_intersection",
            "requested": True, "measured": held, "matched": held,
            "physical_cause_confirmed": False})
    return result
