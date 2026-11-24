"""Source-bound right-turn-lane observations for NRS 484B.223(4)(a).

Lane use, planned purpose, and observed route are separate observations.
"""

def validate_site(site):
    required = {"highway_source", "turn_lane_id", "turn_lane_source",
                "one_right_turn_lane", "exclusive_right_turn", "t_junction_id",
                "entry_road_id", "right_exit_road_id", "connected_route_source",
                "ego_id"}
    if required - site.keys() or not all(site[k] for k in
                                          ("highway_source", "turn_lane_id",
                                           "turn_lane_source", "t_junction_id",
                                           "entry_road_id", "right_exit_road_id",
                                           "connected_route_source", "ego_id")):
        raise ValueError("missing source-bound highway or connected route")
    if not site["one_right_turn_lane"] or not site["exclusive_right_turn"]:
        raise ValueError("single exclusive right-turn-lane design absent")
    if site["entry_road_id"] == site["right_exit_road_id"]:
        raise ValueError("right turn needs a distinct connected exit road")


def measure(site, frames, purpose):
    validate_site(site)
    if set(("declared_purpose", "source_ref", "declared_before_frame")) - purpose.keys() or not purpose["source_ref"]:
        raise ValueError("missing independently sourced purpose")
    if purpose["declared_purpose"] not in ("right_turn", "other"):
        raise ValueError("unknown purpose")
    required = {"original_frame", "time_s", "lane_id", "road_id", "maneuver",
                "source_ref", "driver_id"}
    if len(frames) < 3 or any(required - f.keys() or not f["source_ref"] for f in frames):
        raise ValueError("missing original route source")
    if any(f["driver_id"] != site["ego_id"] for f in frames):
        raise ValueError("vehicle identity mismatch")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("nonmonotone route history")
    occupied = [i for i, f in enumerate(frames) if f["lane_id"] == site["turn_lane_id"]]
    if not occupied:
        raise ValueError("right-turn lane occupancy absent")
    if purpose["declared_before_frame"] >= frames[occupied[0]]["original_frame"]:
        raise ValueError("purpose not sourced before lane entry")
    observed_turn = any(f["maneuver"] == "right_turn" and
                        f["road_id"] == site["right_exit_road_id"] for f in frames)
    return {"lane_occupancy_original_frames": [frames[i]["original_frame"] for i in occupied],
            "declared_purpose": purpose["declared_purpose"],
            "purpose_source": purpose["source_ref"],
            "connected_right_turn_observed": observed_turn,
            "purpose_route_agreement": purpose["declared_purpose"] == "right_turn" and observed_turn,
            "purpose_sufficiency": "unresolved",
            "route_sources": list(dict.fromkeys(f["source_ref"] for f in frames))}
