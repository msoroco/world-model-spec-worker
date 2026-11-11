"""Guarded Native OpenDRIVE load and lane-station verification.

The caller must own world restoration around this mutation. CPU mocks prove
call/validation behavior; only an actual CARLA run can establish ingestibility.
"""

import hashlib
import math
from pathlib import Path

from site_construction import validate_site


def load_verified_world(client, carla, site, source_directory):
    validate_site(site)
    if site["source_status"] != "reviewed_candidate":
        raise ValueError("Unreviewed diagnostic map cannot be loaded")
    ref = site.get("map_source")
    if not isinstance(ref, dict) or ref.get("status") != "reviewed_candidate":
        raise ValueError("Reviewed OpenDRIVE source binding required")
    relative = Path(ref.get("path", ""))
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".xodr":
        raise ValueError("Invalid relative OpenDRIVE source path")
    source_directory = Path(source_directory).resolve()
    path = (source_directory / relative).resolve()
    if not path.is_relative_to(source_directory) or not path.is_file():
        raise ValueError("OpenDRIVE source missing or escapes bundle")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get("sha256"):
        raise ValueError("OpenDRIVE source changed")
    source = raw.decode("utf-8")
    if not source.lstrip().startswith("<OpenDRIVE"):
        raise ValueError("OpenDRIVE root missing")
    client.generate_opendrive_world(source)
    world = client.get_world()
    mapping = world.get_map()
    for name, lane in site["incoming_lanes"].items():
        for row in lane["stations"]:
            xyz = row["xyz_m"]
            waypoint = mapping.get_waypoint(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                            project_to_road=False)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (
                    lane["road_id"], lane["lane_id"]):
                raise ValueError("Native map lane differs from sourced station: " + name)
            location = waypoint.transform.location
            delta = math.dist((location.x, location.y, location.z), xyz)
            if not math.isfinite(delta) or delta > 0.75:
                raise ValueError("Native waypoint differs from sourced station: " + name)
    return world
