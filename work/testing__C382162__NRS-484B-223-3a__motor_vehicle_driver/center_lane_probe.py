"""Source-bound center-turn-lane route observations for NRS 484B.223(3)(a).

Recorded turn purpose is kept distinct from the measured route. This probe does
not infer purpose from distance traveled, lane occupancy, or turn completion.
"""

from center_lane_site import inspect_site


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


def measure_exact(site, case_kind, frames, purpose_record):
    """Measure a sealed original route without turning its purpose into a verdict."""
    topology = inspect_site(site, case_kind)
    if (not isinstance(purpose_record, dict) or
            purpose_record.get("declared_purpose") not in
            {"left_turn_onto_highway", "left_turn_from_highway", "through_travel",
             "right_turn", "left_turn_from_alley"} or
            not purpose_record.get("source_ref") or
            type(purpose_record.get("declared_before_frame")) is not int):
        raise ValueError("independent pre-entry purpose source missing")
    if len(frames) < 3:
        raise ValueError("original route history too short")
    original = [row.get("original_frame") for row in frames]
    if any(type(v) is not int for v in original) or any(
            b != a + 1 for a, b in zip(original, original[1:])):
        raise ValueError("original frame identity discontinuity")
    first_time = float(frames[0].get("time_s", -1000))
    if any(abs(float(row.get("time_s", -1000)) - first_time - index / 20) > .005
           for index, row in enumerate(frames)):
        raise ValueError("original 20 Hz timestamps discontinuous")
    required = ("road_id", "lane_id", "maneuver", "driver_id", "source_ref")
    if any(any(not row.get(name) for name in required) for row in frames):
        raise ValueError("original lane, road, actor or route source missing")
    if len({row["driver_id"] for row in frames}) != 1:
        raise ValueError("original driver identity changed")
    center = topology["center_lane_id"]
    occupied = [row for row in frames if row["lane_id"] == center]
    if not occupied:
        raise ValueError("actual center-lane occupancy absent")
    if purpose_record["declared_before_frame"] >= occupied[0]["original_frame"]:
        raise ValueError("purpose source was not recorded before lane entry")
    road = topology["highway_road_id"]
    relationship = topology["route_relationship"]
    if relationship == "from_highway" and frames[0]["road_id"] != road:
        raise ValueError("observed approach not from highway")
    if relationship == "onto_highway" and frames[-1]["road_id"] != road:
        raise ValueError("observed departure not onto highway")
    left_frames = [row["original_frame"] for row in frames if row["maneuver"] == "left_turn"]
    right_frames = [row["original_frame"] for row in frames if row["maneuver"] == "right_turn"]
    return {
        "case_kind": case_kind,
        "center_lane_occupancy_frames": [row["original_frame"] for row in occupied],
        "observed_left_turn_frames": left_frames,
        "observed_right_turn_frames": right_frames,
        "observed_approach_road_id": frames[0]["road_id"],
        "observed_departure_road_id": frames[-1]["road_id"],
        "declared_purpose": purpose_record["declared_purpose"],
        "purpose_source": purpose_record["source_ref"],
        "junction_kind": topology["junction_kind"],
        "intersection_eligible": topology["junction_kind"] == "street_intersection",
        "route_relationship": relationship,
        "purpose_sufficiency": "unresolved",
        "legal_judgment": None,
        "route_sources": list(dict.fromkeys(row["source_ref"] for row in frames)),
    }
