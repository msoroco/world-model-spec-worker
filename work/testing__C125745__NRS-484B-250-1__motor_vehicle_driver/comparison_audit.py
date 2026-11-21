"""Independent source-only entry-order comparison for the stop-sign cell."""

import hashlib
import json
from pathlib import Path

from crossing_measurements import analyze


FIXED = ("native_map_id", "intersection_id", "ego_highway_id",
         "other_highway_id", "ego_road_id", "other_road_id",
         "native_stop_sign_id", "sign_governance_source",
         "stop_sign_video_source", "intersection_polygon_source",
         "intersection_polygon_xy_m", "stop_sign_erected",
         "stop_sign_governed_road_id")


def _source(root, name):
    path = Path(root) / name
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def compare(other_first_root, ego_first_root, expected_frames=1100):
    """Require a controlled changed order; return measurements, never a verdict."""
    if type(expected_frames) is not int or expected_frames < 3:
        raise ValueError("Expected full frame count required")
    first = analyze(Path(other_first_root))
    second = analyze(Path(ego_first_root))
    left, left_sha = _source(other_first_root, "junction_context.json")
    right, right_sha = _source(ego_first_root, "junction_context.json")
    if any(left.get(key) != right.get(key) for key in FIXED):
        raise ValueError("Fixed stop-sign crossing context changed")
    if len(first["samples"]) != expected_frames or len(second["samples"]) != expected_frames:
        raise ValueError("Incomplete original frame history")
    left_times = [(row["frame"], row["time_s"]) for row in first["samples"]]
    right_times = [(row["frame"], row["time_s"]) for row in second["samples"]]
    if left_times != right_times:
        raise ValueError("Comparison original frame/time sequence changed")
    if first["other_entered_before_ego_observed"] is not True:
        raise ValueError("Other-first source did not measure requested order")
    if second["other_entered_before_ego_observed"] is not False:
        raise ValueError("Ego-first source did not measure requested order")
    if first["first_body_entry"]["ego"]["time_s"] == first["first_body_entry"]["other"]["time_s"] or \
            second["first_body_entry"]["ego"]["time_s"] == second["first_body_entry"]["other"]["time_s"]:
        raise ValueError("Tied entry does not establish order")
    return {"format": "worker-stop-sign-entry-comparison",
            "expected_frames": expected_frames,
            "fixed_context_sha256": [left_sha, right_sha],
            "source_sha256": [first["sources"], second["sources"]],
            "other_first_entries": first["first_body_entry"],
            "ego_first_entries": second["first_body_entry"],
            "official_device_exclusion_judgment": "unresolved",
            "physical_acceptance_claimed": False}


def compare_opposite_left(other_first_root, opposite_left_root, expected_frames=900):
    """Independently compare fixed ego/sign sources and the opposing left turn."""
    from shapely.geometry import MultiPoint, Polygon

    if type(expected_frames) is not int or expected_frames < 3:
        raise ValueError("Expected full frame count required")
    roots = [Path(other_first_root), Path(opposite_left_root)]
    contexts = []
    rows = []
    maps = []
    configs = []
    source_hashes = []
    for root in roots:
        names = ("junction_context.json", "crossing_history.jsonl", "video_frames.jsonl", "config.json")
        if any(not (root / name).is_file() for name in names):
            raise ValueError("Comparison lacks original source")
        source_hashes.append({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                              for name in names})
        contexts.append(json.loads((root / names[0]).read_text()))
        rows.append([json.loads(line) for line in (root / names[1]).read_text().splitlines()])
        maps.append([json.loads(line) for line in (root / names[2]).read_text().splitlines()])
        configs.append(json.loads((root / names[3]).read_text()))
    first, opposite = contexts
    fixed = ("native_map_id", "intersection_id", "ego_highway_id", "ego_road_id",
             "native_stop_sign_id", "sign_governance_source", "stop_sign_video_source",
             "intersection_polygon_source", "intersection_polygon_xy_m",
             "stop_sign_erected", "stop_sign_governed_road_id")
    if any(first.get(key) != opposite.get(key) for key in fixed):
        raise ValueError("Fixed ego stop-sign crossing context changed")
    if first['ego_highway_id'] == first['other_highway_id'] or \
            opposite['ego_highway_id'] != opposite['other_highway_id'] or \
            opposite.get('approach_relation') != 'opposite_directions_same_highway':
        raise ValueError("Highway relation did not change to opposing lanes")
    if opposite.get('other_left_turn_intent') != 'left' or not opposite.get('other_left_turn_route_source'):
        raise ValueError("Opposing left-turn intention lacks source")
    yaw_delta = (opposite.get('other_approach_yaw_deg', 0) -
                 opposite.get('ego_approach_yaw_deg', 0)) % 360
    if abs(yaw_delta - 180) > 15:
        raise ValueError("Source approach headings are not opposing")
    if configs[0].get('cameras') != configs[1].get('cameras') or \
            any(config.get('rate_hz') != 20 or config.get('frames') != expected_frames for config in configs):
        raise ValueError("Fixed source cameras or duration changed")
    if any(len(series) != expected_frames for series in rows + maps):
        raise ValueError("Incomplete comparison frame history")
    for left_row, right_row, left_map, right_map in zip(rows[0], rows[1], maps[0], maps[1]):
        if (left_row['frame'], left_row['time_s']) != (right_row['frame'], right_row['time_s']) or \
                left_map != right_map:
            raise ValueError("Original frame/time or camera join changed")
        if left_row['native_stop_sign_id'] != right_row['native_stop_sign_id'] or \
                left_row['ego']['body_vertices_xy_m'] != right_row['ego']['body_vertices_xy_m'] or \
                left_row['ego']['speed_mps'] != right_row['ego']['speed_mps']:
            raise ValueError("Fixed ego motion or sign changed")
    polygon = Polygon(first['intersection_polygon_xy_m'])
    def entry(series, who):
        inside = [MultiPoint(row[who]['body_vertices_xy_m']).convex_hull.intersects(polygon)
                  for row in series]
        if inside[0]:
            raise ValueError("Comparison entry is left-censored")
        return next((row['frame'] for row, value in zip(series, inside) if value), None)
    entries = [{who: entry(series, who) for who in ('ego', 'other')} for series in rows]
    if any(value is None for pair in entries for value in pair.values()) or \
            any(pair['other'] >= pair['ego'] for pair in entries):
        raise ValueError("Other-first complete-body entries not observed")
    headings = [row['other'].get('heading_yaw_deg') for row in rows[1]]
    if any(type(value) not in (int, float) for value in headings):
        raise ValueError("Original opposing heading history missing")
    turn = (headings[-1] - headings[0] + 180) % 360 - 180
    first_y = sum(point[1] for point in rows[1][0]['other']['body_vertices_xy_m']) / \
        len(rows[1][0]['other']['body_vertices_xy_m'])
    last_y = sum(point[1] for point in rows[1][-1]['other']['body_vertices_xy_m']) / \
        len(rows[1][-1]['other']['body_vertices_xy_m'])
    if turn <= 30 or last_y >= first_y - 2:
        raise ValueError("Original other-body left turn not observed")
    return {"format": "worker-stop-sign-opposite-left-comparison",
            "expected_frames": expected_frames, "source_sha256": source_hashes,
            "entry_frames": entries, "other_heading_change_deg": turn,
            "other_southward_displacement_m": first_y - last_y,
            "official_device_exclusion_judgment": "unresolved",
            "opposite_left_turn_exception_judgment": "unresolved",
            "physical_acceptance_claimed": False}
