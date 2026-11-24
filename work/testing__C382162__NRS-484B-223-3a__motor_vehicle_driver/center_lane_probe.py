"""Source-bound center-turn-lane route observations for NRS 484B.223(3)(a).

Recorded turn purpose is kept distinct from the measured route. This probe does
not infer purpose from distance traveled, lane occupancy, or turn completion.
"""


def validate_site(site):
    required = {"highway_source", "center_lane_id", "center_lane_source",
                "one_shared_center_lane", "turns_only_both_directions",
                "intersection_id", "junction_kind", "ego_id"}
    if required - site.keys() or not all(site[k] for k in
                                          ("highway_source", "center_lane_id",
                                           "center_lane_source", "intersection_id", "ego_id")):
        raise ValueError("missing source-bound highway or lane context")
    if not site["one_shared_center_lane"] or not site["turns_only_both_directions"]:
        raise ValueError("single shared turn-only center lane not established")
    if site["junction_kind"] == "alley":
        raise ValueError("alley junction is not an intersection")


def measure(site, frames, purpose_record):
    validate_site(site)
    required_purpose = {"declared_purpose", "source_ref", "declared_before_frame"}
    if required_purpose - purpose_record.keys() or not purpose_record["source_ref"]:
        raise ValueError("missing independently sourced purpose record")
    if purpose_record["declared_purpose"] not in (
            "left_turn_onto_highway", "left_turn_from_highway", "other"):
        raise ValueError("unknown declared purpose")
    required_frame = {"original_frame", "time_s", "lane_id", "road_id",
                      "maneuver", "source_ref", "driver_id"}
    if len(frames) < 3 or any(required_frame - f.keys() or not f["source_ref"]
                              for f in frames):
        raise ValueError("missing original route source")
    if any(f["driver_id"] != site["ego_id"] for f in frames):
        raise ValueError("driver identity mismatch")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("nonmonotone original route")
    occupied = [i for i, f in enumerate(frames) if f["lane_id"] == site["center_lane_id"]]
    if not occupied:
        raise ValueError("center lane occupancy absent")
    if purpose_record["declared_before_frame"] >= frames[occupied[0]]["original_frame"]:
        raise ValueError("purpose record not established before center-lane entry")
    turns = [f["original_frame"] for f in frames if f["maneuver"] == "left_turn"]
    return {
        "center_lane_occupancy_frames": [frames[i]["original_frame"] for i in occupied],
        "observed_left_turn_frames": turns,
        "declared_purpose": purpose_record["declared_purpose"],
        "purpose_source": purpose_record["source_ref"],
        "route_matches_declared_left_turn": bool(turns) and purpose_record["declared_purpose"].startswith("left_turn_"),
        "purpose_sufficiency": "unresolved",
        "route_sources": list(dict.fromkeys(f["source_ref"] for f in frames)),
    }
