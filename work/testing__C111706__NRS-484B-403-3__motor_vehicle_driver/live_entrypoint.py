"""Connect an independently reviewed exact U-turn site to lazy CARLA APIs.

The site packet supplies original map and district sources, route samples,
spawn transforms and four camera poses. This adapter never invents geometry.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from capture_cameras import VIEWS
from construct import load_site
from run_exact import run_exact


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_site_sources(site_path: Path, site: dict, live_map) -> dict:
    """Bind the site to four original documents and the loaded OpenDRIVE map.

    Source files live alongside the reviewed site packet; arbitrary outside
    paths and symlinks are rejected. A district document is retained for
    independent statutory review, never treated as a legal conclusion here.
    """
    import json

    site_path = Path(site_path)
    documents = site.get("source_documents")
    if not isinstance(documents, dict) or set(documents) != {
            "map", "routes", "district", "boundary"}:
        raise ValueError("four reviewed site source documents required")
    expected = {"map": "map_sha256", "routes": "route_sha256",
                "district": "district_source_sha256",
                "boundary": "intersection_boundary_source_sha256"}
    sources = {}
    for name, key in expected.items():
        entry = documents[name]
        if not isinstance(entry, dict) or not entry.get("path"):
            raise ValueError("reviewed source path missing: " + name)
        rel = Path(entry["path"])
        if rel.is_absolute() or len(rel.parts) != 1 or rel.name in (".", ".."):
            raise ValueError("reviewed source path escapes site directory: " + name)
        path = site_path.parent / rel
        if not path.is_file() or path.is_symlink():
            raise ValueError("reviewed source file missing: " + name)
        digest = _sha(path)
        if digest != entry.get("sha256") or digest != site.get(key):
            raise ValueError("reviewed source hash differs: " + name)
        sources[name] = path
    boundary = json.loads(sources["boundary"].read_text(encoding="utf-8"))
    if boundary.get("polygon_xy_m") != site.get("intersection_boundary", {}).get("polygon_xy_m"):
        raise ValueError("reviewed boundary polygon differs")
    if site["intersection_boundary"].get("source_sha256") != site["intersection_boundary_source_sha256"]:
        raise ValueError("boundary source hash binding differs")
    routes = json.loads(sources["routes"].read_text(encoding="utf-8"))
    for key in ("ego_route", "other_route", "ego_spawn", "other_spawn",
                "other_start_tick", "cameras"):
        if routes.get(key) != site.get(key):
            raise ValueError("reviewed route or camera source differs: " + key)
    district = json.loads(sources["district"].read_text(encoding="utf-8"))
    if not district.get("frontage_sources") or not district.get("building_use_sources"):
        raise ValueError("business-district review sources incomplete")
    if live_map.name != site.get("map_name"):
        raise ValueError("reviewed map name differs")
    if hashlib.sha256(live_map.to_opendrive().encode("utf-8")).hexdigest() != site["map_sha256"]:
        raise ValueError("live OpenDRIVE map differs from reviewed source")
    return sources


def _number(value, field):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    import math
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return float(value)


def transform(carla, packet: dict):
    """Build a CARLA transform only from all six source-reviewed coordinates."""
    if not isinstance(packet, dict):
        raise ValueError("reviewed transform packet required")
    xyz = [_number(packet.get(k), k) for k in ("x", "y", "z")]
    angles = [_number(packet.get(k), k) for k in ("pitch", "yaw", "roll")]
    return carla.Transform(carla.Location(*xyz), carla.Rotation(*angles))


def camera_builder(carla, world, actors, site):
    """Spawn four owned sensors with exact sizes and source-specified poses."""
    cameras = site.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four reviewed camera poses required")
    library = world.get_blueprint_library()
    spawned = {}
    try:
        for name, (width, height) in VIEWS.items():
            spec = cameras[name]
            if spec.get("attachment") not in ("world", "ego"):
                raise ValueError("camera attachment must be world or ego")
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("sensor_tick", "0.05")
            bp.set_attribute("fov", str(_number(spec.get("fov_deg"), "fov_deg")))
            pose = transform(carla, spec.get("transform"))
            parent = actors["ego"] if spec["attachment"] == "ego" else None
            sensor = world.spawn_actor(bp, pose, attach_to=parent)
            if sensor is None:
                raise ValueError("camera spawn failed: " + name)
            spawned[name] = sensor
        return spawned
    except Exception:
        for sensor in spawned.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
        raise


def run(*, host: str, port: int, site_path: Path, case_id: str,
        output: Path, carla_module=None):
    """Run one exact attempt; connection is deferred until called."""
    if carla_module is None:
        import carla as carla_module
    site_path = Path(site_path)
    site = load_site(site_path, _sha(site_path), expected_case=case_id)
    for key in ("ego_spawn", "other_spawn", "cameras"):
        if key not in site:
            raise ValueError("reviewed site missing " + key)
    ego_spawn = transform(carla_module, site["ego_spawn"])
    other_spawn = transform(carla_module, site["other_spawn"])
    client = carla_module.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    verify_site_sources(site_path, site, world.get_map())
    return run_exact(world, site_path=site_path, site_sha256=_sha(site_path),
                     case_id=case_id, ego_spawn=ego_spawn,
                     other_spawn=other_spawn,
                     camera_builder=lambda world_, actors_, site_: camera_builder(
                         carla_module, world_, actors_, site_),
                     output=Path(output), control_factory=carla_module.VehicleControl)
