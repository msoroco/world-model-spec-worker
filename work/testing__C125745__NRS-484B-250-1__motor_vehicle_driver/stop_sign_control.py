"""Find a Native stop-sign actor whose trigger contains the approach point.

This tests physical sign governance. Official status and properly erected face
still need Native map and original-camera review.
"""

import math
from contextlib import contextmanager

from shapely.geometry import Point, Polygon


def _pose(value, label):
    if (not isinstance(value, list) or len(value) != 4 or
            any(type(n) not in (int, float) or not math.isfinite(n) for n in value)):
        raise ValueError("Finite x,y,z,yaw pose required: " + label)
    return value


def validate_site(site):
    """Validate reviewed construction inputs without treating them as Native proof."""
    if not isinstance(site, dict):
        raise ValueError("Reviewed site packet required")
    for key in ("native_map_name", "crossing_source", "median_opening_source",
                "different_highways_source", "device_inventory_source",
                "sign_erection_source", "camera_plan_source"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("Missing site source: " + key)
    if type(site.get("junction_id")) is not int:
        raise ValueError("Native junction identity required")
    highways = site.get("highway_ids")
    if (not isinstance(highways, dict) or set(highways) != {"ego", "other"} or
            not all(isinstance(v, str) and v for v in highways.values()) or
            highways["ego"] == highways["other"]):
        raise ValueError("Distinct sourced highway identities required")
    for role in ("ego", "other"):
        for phase in ("approach", "entry"):
            _pose(site.get(role + "_" + phase), role + " " + phase)
    coords = site.get("crossing_polygon_xy_m")
    if not isinstance(coords, list) or len(coords) < 3:
        raise ValueError("Sourced crossing polygon required")
    for pair in coords:
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in pair)):
            raise ValueError("Finite crossing polygon vertex required")
    polygon = Polygon(coords)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid crossing polygon required")
    for role in ("ego", "other"):
        approach = site[role + "_approach"]
        entry = site[role + "_entry"]
        if polygon.intersects(Point(approach[:2])) or not polygon.contains(Point(entry[:2])):
            raise ValueError("Approach outside and entry inside crossing required: " + role)
        dx, dy = entry[0] - approach[0], entry[1] - approach[1]
        if dx * math.cos(math.radians(approach[3])) + dy * math.sin(math.radians(approach[3])) <= 0:
            raise ValueError("Approach points away from crossing: " + role)
    return polygon


def _waypoint(world_map, transform):
    waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError("Native pose does not lie on a road")
    return waypoint


@contextmanager
def construct_candidate(world, site, transforms, blueprint):
    """Check both Native approaches and own both spawned vehicle lifetimes.

    Site source strings identify review inputs. This code cannot certify that a
    sign is official, properly erected or visible in original camera pixels.
    """
    validate_site(site)
    world_map = world.get_map()
    if world_map.name != site["native_map_name"]:
        raise ValueError("Native map differs from reviewed site")
    waypoints = {key: _waypoint(world_map, transforms[key]) for key in
                 ("ego_approach", "ego_entry", "other_approach", "other_entry")}
    if waypoints["ego_approach"].road_id == waypoints["other_approach"].road_id:
        raise ValueError("Different Native approach roads required")
    for role in ("ego", "other"):
        entry = waypoints[role + "_entry"]
        junction = entry.get_junction() if entry.is_junction else None
        if junction is None or junction.id != site["junction_id"]:
            raise ValueError("Entry outside selected Native junction: " + role)
    sign_waypoint = (waypoints["ego_approach"] if "ego_sign_check" not in transforms
                     else _waypoint(world_map, transforms["ego_sign_check"]))
    if sign_waypoint.road_id != waypoints["ego_approach"].road_id:
        raise ValueError("Stop sign check is not on ego approach road")
    sign = find_governing_stop_sign(world, sign_waypoint)
    if sign.trigger_volume.contains(waypoints["other_approach"].transform.location,
                                    sign.get_transform()):
        raise ValueError("Selected sign also governs other approach")
    actors = []
    try:
        for role in ("ego", "other"):
            actor = world.try_spawn_actor(blueprint, transforms[role + "_approach"])
            if actor is None:
                raise ValueError("Native vehicle spawn failed: " + role)
            actors.append(actor)
        yield {"ego": actors[0], "other": actors[1], "stop_sign": sign,
               "junction_id": site["junction_id"],
               "approach_road_ids": {role: waypoints[role + "_approach"].road_id
                                     for role in ("ego", "other")},
               "highway_ids": site["highway_ids"]}
    finally:
        for actor in reversed(actors):
            actor.destroy()


def find_governing_stop_sign(world, approach_waypoint):
    point = approach_waypoint.transform.location
    matches = []
    for sign in world.get_actors().filter("traffic.stop*"):
        if sign.trigger_volume.contains(point, sign.get_transform()):
            matches.append(sign)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing stop sign, found {len(matches)}")
    return matches[0]


# Hash-bound C125745 median-site adapter shared by subsection (1) constructions.
"""Bind the subsection (1) construction to the same C125745 median-site sources.

The source site is synthetic.  This is a CPU construction input and provenance
check, not evidence that the sign is official or that Native motion occurred.
"""

import hashlib
import json
from pathlib import Path



SIBLING = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver"
SITE_SHA256 = "a72765662459a1dd85101835279c82c74c6c711fcf212ba8035085c813765872"
CLAIMS = {
    "crossing_geometry_source": ("native_map_name", "intersection_id",
                                 "crossing_polygon_xy_m", "same_statutory_crossing"),
    "all_entrances_source": ("intersection_id", "all_entrance_road_lanes"),
    "sign_governance_source": ("stop_sign", "all_entrance_road_lanes"),
    "sign_face_video_source": ("stop_sign",),
    "median_spacing_source": ("intersection_id", "same_statutory_crossing"),
}


def _read_bound(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("C125745 site source SHA mismatch: " + str(path))
    return json.loads(data)


def load_site(root=None):
    """Return subsection (1) poses, governance sources and four camera poses.

    The two statutory subsections use the same selected C125745 junction and
    sign, so only physical site fields are reused.  Legal predicates are not.
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    sibling = (root / SIBLING).resolve()
    if not sibling.is_relative_to(root.resolve()):
        raise ValueError("Site source escaped work root")
    if not (sibling / "site.json").is_file():
        bundled = Path(__file__).resolve().parent
        if (bundled / "site.json").is_file():
            sibling = bundled
    source = _read_bound(sibling / "site.json", SITE_SHA256)
    if (source.get("format") != "worker-stop-median-site-review" or
            source.get("review_status") != "reviewed_candidate" or
            source.get("approach_relation") != "different_highways" or
            source.get("same_statutory_crossing") is not True or
            set(source.get("camera_poses", {})) !=
            {"overview", "approach", "reference_corner", "driver_reference"}):
        raise ValueError("Expected C125745 median stop-sign scene missing")
    refs = source.get("source_refs")
    docs = source.get("source_documents")
    if not isinstance(refs, dict) or not isinstance(docs, dict) or set(refs) != set(CLAIMS) or set(docs) != set(CLAIMS):
        raise ValueError("Complete sourced site inventory required")
    for role, keys in CLAIMS.items():
        ref = docs[role]
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError("Hashed site review source required: " + role)
        relative = Path(ref["path"])
        path = (sibling / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(sibling):
            raise ValueError("Site review source escaped assignment")
        if refs[role] != relative.as_posix():
            raise ValueError("Site review source path differs: " + role)
        document = _read_bound(path, ref["sha256"])
        if (document.get("format") != "worker-stop-median-site-source" or
                document.get("source_role") != role or
                not document.get("review_basis") or
                not isinstance(document.get("reviewed_site_fields"), dict)):
            raise ValueError("Structured site review source required: " + role)
        claims = document["reviewed_site_fields"]
        if not set(keys) <= set(claims) or any(source.get(k) != v for k, v in claims.items()):
            raise ValueError("Site claim differs from review source: " + role)
    ego, other = (source["approaches"][role] for role in ("ego", "other"))
    if (ego["highway_id"] == other["highway_id"] or
            ego["road_id"] == other["road_id"] or
            source["stop_sign"]["governed_lane_id"] != ego["lane_id"]):
        raise ValueError("Distinct approach highways and ego sign governance required")
    center = [15, 0, 0]
    site = {
        "native_map_name": source["native_map_name"],
        "junction_id": source["intersection_id"],
        "highway_ids": {"ego": ego["highway_id"], "other": other["highway_id"]},
        "ego_approach": ego["spawn_pose"],
        "ego_entry": center + [ego["spawn_pose"][3]],
        "other_approach": other["spawn_pose"],
        "other_entry": center + [other["spawn_pose"][3]],
        "crossing_polygon_xy_m": source["crossing_polygon_xy_m"],
        "ego_stop_line_xy_m": source["ego_stop_line_xy_m"],
        "crossing_source": refs["crossing_geometry_source"],
        "median_opening_source": refs["median_spacing_source"],
        "different_highways_source": refs["all_entrances_source"],
        "device_inventory_source": refs["all_entrances_source"],
        "sign_erection_source": refs["sign_governance_source"],
        "camera_plan_source": refs["sign_face_video_source"],
        "camera_poses": source["camera_poses"],
        "stop_sign_native_id": source["stop_sign"]["native_id"],
        "site_source": str((sibling / "site.json").relative_to(root)),
        "site_source_sha256": SITE_SHA256,
        "review_status": "synthetic_cpu_candidate",
    }
    validate_site(site)
    return site
