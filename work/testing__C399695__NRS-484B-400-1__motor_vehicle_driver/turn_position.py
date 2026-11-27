"""Source-bound observations for NRS 484B.400(1) at a T junction.

The approach and the right turn are separate measured intervals.  The
right-turn-lane qualification is a reviewed source fact, never inferred from
lane occupancy or a painted arrow in a synthetic fixture.
"""

import math


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_site(site):
    for key in ("source_id", "map_sha256", "public_highway_source", "intersection_source",
                "right_lane_design_source", "qualification_223_4_source",
                "connected_right_exit_source", "driver_identity_source", "driver_id",
                "entry_road_id", "right_exit_road_id", "junction_id", "turn_lane_id"):
        _need(site.get(key), "missing original site source: " + key)
    _need(site.get("public_highway") is True and site.get("non_alley_intersection") is True,
          "public-highway non-alley intersection source required")
    _need(site.get("t_intersection") is True and site.get("connected_right_exit") is True,
          "connected T-junction right exit source required")
    _need(type(site.get("right_turn_lane_qualified_under_223_4")) is bool,
          "reviewed NRS 484B.223(4) lane qualification required")
    _need(site["entry_road_id"] != site["right_exit_road_id"],
          "right exit must be a distinct connected road")
    _need(site.get("extreme_right_lane_id") is not None,
          "source-surveyed extreme-right lane required")
    if site["right_turn_lane_qualified_under_223_4"]:
        _need(site["extreme_right_lane_id"] != site["turn_lane_id"],
              "separate extreme-right lane required for the controlled comparison")


def measure(site, frames, intention):
    """Measure lane position during approach and turn from original frame rows."""
    validate_site(site)
    _need(intention.get("maneuver") == "right_turn" and intention.get("source_ref") and
          type(intention.get("declared_before_frame")) is int,
          "independent pre-approach right-turn intention required")
    _need(len(frames) >= 4, "original approach, turn and exit samples required")
    required = {"original_frame", "time_s", "driver_id", "road_id", "lane_id",
                "junction_id", "phase", "source_ref", "position_xyz_m"}
    for index, row in enumerate(frames):
        _need(not (required - row.keys()) and row["source_ref"],
              "missing original lane/phase/pose source")
        _need(row["driver_id"] == site["driver_id"], "driver identity mismatch")
        _need(type(row["original_frame"]) is int and _finite(row["time_s"]),
              "invalid original frame or time")
        _need(isinstance(row["position_xyz_m"], list) and len(row["position_xyz_m"]) == 3 and
              all(_finite(value) for value in row["position_xyz_m"]),
              "missing original body position")
        if index:
            previous = frames[index - 1]
            _need(previous["original_frame"] < row["original_frame"] and
                  previous["time_s"] < row["time_s"], "nonmonotone original frames")
    approach = [r for r in frames if r["phase"] == "approach"]
    turn = [r for r in frames if r["phase"] == "right_turn"]
    departure = [r for r in frames if r["phase"] == "departure"]
    _need(approach and turn and departure, "approach, turn and departure intervals required")
    _need(max(r["original_frame"] for r in approach) < min(r["original_frame"] for r in turn) and
          max(r["original_frame"] for r in turn) < min(r["original_frame"] for r in departure),
          "approach, turn and departure order differs")
    _need(intention["declared_before_frame"] < approach[0]["original_frame"],
          "right-turn intention not sourced before approach")
    _need(all(r["road_id"] == site["entry_road_id"] for r in approach) and
          all(r["junction_id"] == site["junction_id"] for r in turn) and
          all(r["road_id"] == site["right_exit_road_id"] for r in departure),
          "T-junction road and connected exit trace mismatch")
    required_lane = site["turn_lane_id"] if site["right_turn_lane_qualified_under_223_4"] else site["extreme_right_lane_id"]
    return {
        "qualifying_right_turn_lane": site["right_turn_lane_qualified_under_223_4"],
        "conditional_lane_id": required_lane,
        "approach_lane_ids": [r["lane_id"] for r in approach],
        "turn_lane_ids": [r["lane_id"] for r in turn],
        "approach_entirely_from_required_lane": all(r["lane_id"] == required_lane for r in approach),
        "turn_entirely_from_required_lane": all(r["lane_id"] == required_lane for r in turn),
        "approach_original_frames": [r["original_frame"] for r in approach],
        "turn_original_frames": [r["original_frame"] for r in turn],
        "intention_source": intention["source_ref"],
        "site_sources": {key: site[key] for key in
                         ("public_highway_source", "intersection_source", "right_lane_design_source",
                          "qualification_223_4_source", "connected_right_exit_source",
                          "driver_identity_source")},
        "frame_sources": list(dict.fromkeys(r["source_ref"] for r in frames)),
        "legal_verdict": None,
    }
