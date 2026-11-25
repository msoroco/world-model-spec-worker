"""Acquire and verify the original Native intersection and rider asset sources.

The requested route is only a survey target. A packet is usable after the
loaded OpenDRIVE, every projected waypoint and the rider asset review are
bound to original bytes. No source label alone establishes rider visibility.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil

_SPEC = importlib.util.spec_from_file_location("cyclist_encounter", Path(__file__).with_name("cyclist_encounter.py"))
_ENCOUNTER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ENCOUNTER)
RIDER_KINDS = _ENCOUNTER.RIDER_KINDS
validate_site = _ENCOUNTER.validate_site


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_ref(root, ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("sealed source reference required")
    path = root / ref["path"]
    if path.is_symlink() or path.resolve().parent != root.resolve() or not path.is_file():
        raise ValueError("original source outside survey")
    if _sha(path) != ref["sha256"]:
        raise ValueError("original source hash drift")
    return path


def _write(root, name, content):
    path = root / name
    if path.exists():
        raise ValueError("survey source already exists")
    path.write_text(content, encoding="utf-8")
    return {"path": name, "sha256": _sha(path)}


def _waypoint(map_obj, carla, point, junction_id, snap_m):
    if not isinstance(point, list) or len(point) != 2:
        raise ValueError("requested route point malformed")
    xy = [float(value) for value in point]
    if not all(math.isfinite(value) for value in xy):
        raise ValueError("requested route point nonfinite")
    native = map_obj.get_waypoint(carla.Location(x=xy[0], y=xy[1], z=0.0), project_to_road=True)
    if native is None:
        raise ValueError("Native waypoint unavailable")
    loc = native.transform.location
    actual = [float(loc.x), float(loc.y)]
    z_m = float(loc.z)
    yaw_deg = float(native.transform.rotation.yaw)
    if not math.isfinite(z_m) or not math.isfinite(yaw_deg):
        raise ValueError("Native waypoint transform nonfinite")
    if math.dist(xy, actual) > snap_m:
        raise ValueError("requested route misses Native waypoint")
    if not isinstance(native.road_id, int) or not isinstance(native.lane_id, int):
        raise ValueError("original road/lane identity missing")
    native_junction = native.get_junction() if native.is_junction else None
    return {"x_m": actual[0], "y_m": actual[1], "road_id": native.road_id,
            "z_m": z_m, "yaw_deg": yaw_deg,
            "lane_id": native.lane_id, "junction_id": native_junction.id if native_junction else None,
            "source_ref": "original_native_waypoint", "requested_xy": xy,
            "native_waypoint_id": native.id}


def survey(world, carla, request, output_dir):
    """Seal loaded map and projected routes; require an independently reviewed rider asset.

    The caller supplies a local rider-review JSON path and its expected SHA256.
    Its contents identify a source asset; they do not prove physical visibility.
    """
    kind = request.get("rider_kind")
    if kind not in RIDER_KINDS:
        raise ValueError("unsupported rider kind")
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("survey output must be empty")
    map_obj = world.get_map()
    xodr = map_obj.to_opendrive()
    if not isinstance(xodr, str) or len(xodr) < 10:
        raise ValueError("original OpenDRIVE missing")
    map_ref = _write(root, "native-map.xodr", xodr)
    asset_input = Path(request["rider_asset_review_path"])
    asset = asset_input.resolve()
    if asset_input.is_symlink() or not asset.is_file() or _sha(asset) != request.get("rider_asset_review_sha256"):
        raise ValueError("reviewed rider asset source missing or stale")
    review = json.loads(asset.read_text(encoding="utf-8"))
    if (review.get("format") != "c111260-reviewed-rider-asset-v1"
            or review.get("kind") != kind or not review.get("asset_source_sha256")
            or not review.get("asset_source_path")
            or not review.get("person_actor_id") or not review.get("blueprint_id")):
        raise ValueError("reviewed rider asset identity missing")
    asset_input = Path(review["asset_source_path"])
    asset_source = asset_input.resolve()
    if (asset_input.is_symlink() or not asset_source.is_file()
            or _sha(asset_source) != review["asset_source_sha256"]):
        raise ValueError("reviewed rider asset bytes missing or stale")
    library = world.get_blueprint_library()
    rider_blueprint = library.find(review["blueprint_id"])
    motor_blueprint = library.find(request["motor_blueprint_id"])
    if (rider_blueprint is None or rider_blueprint.id != review["blueprint_id"]
            or motor_blueprint is None or motor_blueprint.id != request["motor_blueprint_id"]):
        raise ValueError("reviewed Native blueprints unavailable")
    rider_ref = _write(root, "rider-asset-review.json", asset.read_text(encoding="utf-8"))
    native_asset = root / "rider-asset.source"
    shutil.copyfile(asset_source, native_asset)
    native_asset_ref = {"path": native_asset.name, "sha256": _sha(native_asset)}
    snap_m = float(request.get("max_waypoint_snap_m", 1.5))
    if not math.isfinite(snap_m) or not 0 < snap_m <= 2:
        raise ValueError("invalid Native waypoint snap limit")
    junction = request.get("junction_id")
    if junction is None:
        raise ValueError("original junction ID required")
    routes = {}
    for name in ("ego_route", "rider_route"):
        points = request.get(name + "_xy")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("approach, conflict and exit route required")
        routes[name] = [_waypoint(map_obj, carla, point, junction, snap_m) for point in points]
        if not routes[name][1]["junction_id"] == junction:
            raise ValueError("Native conflict waypoint junction mismatch")
    packet = {"map_sha256": map_ref["sha256"], "map_source_ref": map_ref,
              "native_map_name": map_obj.name, "junction_id": junction,
              "ego_route": routes["ego_route"], "rider_route": routes["rider_route"],
              "motor_vehicle": {"source_ref": "original_blueprint_library", "blueprint_id": motor_blueprint.id,
                                "rail_bound": False},
              "rider": {"source_ref": rider_ref, "blueprint_id": rider_blueprint.id,
                        "asset_source_ref": native_asset_ref,
                        "person_actor_id": review["person_actor_id"], "kind": kind,
                        "moped": review.get("moped", False),
                        "motorized": review.get("motorized", False),
                        "wheel_diameters_in": review.get("wheel_diameters_in", []),
                        "electric_assist": review.get("electric_assist", False),
                        "standing_platform": review.get("standing_platform", False)},
              "physical_visibility": "pending"}
    validate_site(packet, kind)
    site_ref = _write(root, "site-survey.json", json.dumps(packet, sort_keys=True, indent=2) + "\n")
    return {"site": site_ref, "original_map": map_ref, "rider_review": rider_ref}


def verify(root, ref, *, expected_kind):
    root = Path(root).resolve()
    packet = json.loads(_read_ref(root, ref).read_text(encoding="utf-8"))
    map_ref = packet["map_source_ref"]
    _read_ref(root, map_ref)
    if packet["map_sha256"] != map_ref["sha256"]:
        raise ValueError("site OpenDRIVE binding changed")
    rider_ref = packet["rider"]["source_ref"]
    review = json.loads(_read_ref(root, rider_ref).read_text(encoding="utf-8"))
    rider = packet["rider"]
    native_asset = rider.get("asset_source_ref")
    if not native_asset or native_asset["sha256"] != review.get("asset_source_sha256"):
        raise ValueError("site rider asset bytes changed")
    _read_ref(root, native_asset)
    if (review.get("format") != "c111260-reviewed-rider-asset-v1"
            or review.get("kind") != expected_kind
            or review.get("blueprint_id") != rider["blueprint_id"]
            or review.get("person_actor_id") != rider["person_actor_id"]
            or review.get("moped", False) != rider["moped"]
            or review.get("motorized", False) != rider["motorized"]
            or review.get("wheel_diameters_in", []) != rider["wheel_diameters_in"]
            or review.get("electric_assist", False) != rider["electric_assist"]
            or review.get("standing_platform", False) != rider["standing_platform"]):
        raise ValueError("site rider review binding changed")
    if packet.get("physical_visibility") != "pending":
        raise ValueError("site cannot assert physical visibility")
    validate_site(packet, expected_kind)
    return packet


def verify_live(world, carla, root, ref, *, expected_kind, snap_m=0.25):
    """Reject a survey from another loaded world before any actor is spawned."""
    packet = verify(root, ref, expected_kind=expected_kind)
    map_obj = world.get_map()
    if (map_obj.name != packet["native_map_name"]
            or hashlib.sha256(map_obj.to_opendrive().encode("utf-8")).hexdigest() != packet["map_sha256"]):
        raise ValueError("loaded Native map differs from sealed survey")
    if not 0 < snap_m <= 0.5:
        raise ValueError("invalid live waypoint tolerance")
    for route in ("ego_route", "rider_route"):
        for saved in packet[route]:
            location = carla.Location(x=saved["x_m"], y=saved["y_m"], z=0.0)
            current = map_obj.get_waypoint(location, project_to_road=True)
            if current is None:
                raise ValueError("surveyed Native waypoint disappeared")
            actual = current.transform.location
            rotation = current.transform.rotation
            junction = current.get_junction() if current.is_junction else None
            if (math.dist((saved["x_m"], saved["y_m"]), (float(actual.x), float(actual.y))) > snap_m
                    or saved["road_id"] != current.road_id
                    or saved["lane_id"] != current.lane_id
                    or saved["junction_id"] != (junction.id if junction else None)
                    or saved["native_waypoint_id"] != current.id):
                raise ValueError("surveyed Native waypoint changed")
            if (abs(saved["z_m"] - float(actual.z)) > snap_m
                    or abs((saved["yaw_deg"] - float(rotation.yaw) + 180) % 360 - 180) > 1.0):
                raise ValueError("surveyed Native waypoint transform changed")
    library = world.get_blueprint_library()
    for role in ("motor_vehicle", "rider"):
        blueprint = library.find(packet[role]["blueprint_id"])
        if blueprint is None or blueprint.id != packet[role]["blueprint_id"]:
            raise ValueError("reviewed Native blueprint changed")
    return packet
