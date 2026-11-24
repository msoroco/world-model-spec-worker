"""Source-bound crossing observations for NRS 484B.587(1).

Access designation and official notice come from authority/device sources; a
map road type alone is insufficient to establish controlled-access status.
"""

from math import isfinite


def validate_site(site):
    required = {"authority_source", "highway_source", "boundary_source",
                "controlled_access_determination", "boundary_x_m", "indicated_points",
                "official_notice_source", "vehicle_id"}
    if required - site.keys() or not all(site[k] for k in
                                          ("authority_source", "highway_source",
                                           "boundary_source", "official_notice_source",
                                           "vehicle_id")):
        raise ValueError("missing authority, highway boundary or device source")
    if not site["controlled_access_determination"]:
        raise ValueError("controlled-access status not established")
    if not isfinite(site["boundary_x_m"]) or not site["indicated_points"]:
        raise ValueError("missing access boundary or indicated points")
    for point in site["indicated_points"]:
        if set(("point_id", "direction", "y_min_m", "y_max_m", "device_id",
                "device_source", "erected", "notice_visible")) - point.keys():
            raise ValueError("incomplete indicated access point")
        if not point["device_source"] or not point["device_id"] or not point["erected"]:
            raise ValueError("official device not established")
        if point["direction"] not in ("entry", "exit") or point["y_min_m"] > point["y_max_m"]:
            raise ValueError("invalid access point geometry")


def measure(site, frames):
    validate_site(site)
    required = {"original_frame", "time_s", "vehicle_id", "xy", "source_ref"}
    if len(frames) < 2 or any(required - f.keys() or not f["source_ref"] for f in frames):
        raise ValueError("missing original vehicle route")
    if any(f["vehicle_id"] != site["vehicle_id"] for f in frames):
        raise ValueError("vehicle identity mismatch")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("nonmonotone original route")
    if any(len(f["xy"]) != 2 or not all(isfinite(v) for v in f["xy"]) for f in frames):
        raise ValueError("invalid route position")
    boundary = site["boundary_x_m"]
    crossings = []
    for prior, current in zip(frames, frames[1:]):
        x0, y0 = prior["xy"]
        x1, y1 = current["xy"]
        if (x0 < boundary <= x1) or (x1 < boundary <= x0):
            direction = "entry" if x1 > x0 else "exit"
            y_cross = y0 + (y1 - y0) * (boundary - x0) / (x1 - x0)
            matching = [p for p in site["indicated_points"]
                        if p["direction"] == direction and p["notice_visible"] and
                        p["y_min_m"] <= y_cross <= p["y_max_m"]]
            crossings.append({"original_frame": current["original_frame"],
                              "direction": direction, "crossing_y_m": y_cross,
                              "indicated_point_ids": [p["point_id"] for p in matching]})
    if not crossings:
        raise ValueError("highway boundary crossing not observed")
    return {"crossings": crossings,
            "all_crossings_at_indicated_points": all(c["indicated_point_ids"] for c in crossings),
            "source_refs": sorted(set([site[k] for k in
                                       ("authority_source", "highway_source",
                                        "boundary_source", "official_notice_source")] +
                                      [f["source_ref"] for f in frames] +
                                      [p["device_source"] for p in site["indicated_points"]]))}
