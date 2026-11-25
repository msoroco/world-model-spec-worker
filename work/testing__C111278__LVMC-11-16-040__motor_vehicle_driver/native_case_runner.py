"""Source-gated operator entry point for one LVMC 11.16.040 Native case.

The operator supplies the CARLA world, ego, original readers and camera adapter.
No CARLA dependency is imported by this module or by its CPU tests.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from sight_construction import CASES, spawn_occluder, validate_site
from native_sight_capture import capture
from native_route_reader import ReviewedRouteReader
from native_speed_controller import NativeSpeedController
from native_ray_reader import ReviewedRayReader


SOURCE_FIELDS = ("jurisdiction", "road_kind", "entering_arms", "ego_road_through",
                 "traffic_controlled_intersection", "boundary")


def read_reviewed_site(packet_path: Path, *, case_key: str, world) -> dict:
    if case_key not in CASES:
        raise ValueError("Unknown exact case")
    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if packet.get("case_id") != case_key or not packet.get("reviewer"):
        raise ValueError("Reviewed site identity or reviewer missing")
    if packet.get("map_hash") != hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest():
        raise ValueError("Reviewed OpenDRIVE map hash mismatch")
    refs = packet.get("source_files")
    if not isinstance(refs, dict):
        raise ValueError("Reviewed source inventory missing")
    for field in SOURCE_FIELDS:
        ref = refs.get(field)
        if not isinstance(ref, dict):
            raise ValueError("Reviewed source missing: " + field)
        name = ref.get("path")
        if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise ValueError("Unsafe reviewed source path")
        source = packet_path.parent / name
        parts = [packet_path.parent.joinpath(*Path(name).parts[:i])
                 for i in range(1, len(Path(name).parts) + 1)]
        if any(part.is_symlink() for part in parts):
            raise ValueError("Symlinked reviewed source path")
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref.get("sha256") or digest != packet.get(field + "_source_sha256"):
            raise ValueError("Reviewed source hash mismatch: " + field)
        document = json.loads(data)
        expected_value = (packet.get("intersection_boundary_xy") if field == "boundary"
                          else packet.get(field))
        if (document.get("source_kind") != field or not document.get("reviewer")
                or not document.get("source_citation")
                or document.get("value") != expected_value):
            raise ValueError("Reviewed source claim mismatch: " + field)
        if field == "boundary" and (not isinstance(expected_value, list) or
                len(expected_value) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in expected_value)):
            raise ValueError("Reviewed intersection boundary coordinate invalid")
    if CASES[case_key].occluder:
        field = "occluder_sites"
        ref = refs.get(field)
        if not isinstance(ref, dict):
            raise ValueError("reviewed occluder placement source missing")
        name = ref.get("path")
        if (not isinstance(name, str) or not name or Path(name).is_absolute() or
                ".." in Path(name).parts or "\\" in name):
            raise ValueError("unsafe reviewed occluder source path")
        source = packet_path.parent / name
        if any(part.is_symlink() for part in
               [packet_path.parent.joinpath(*Path(name).parts[:i])
                for i in range(1, len(Path(name).parts) + 1)]):
            raise ValueError("symlinked reviewed occluder source path")
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != ref.get("sha256") or digest != packet.get("occluder_sites_source_sha256"):
            raise ValueError("reviewed occluder source hash mismatch")
        doc = json.loads(raw)
        if (doc.get("source_kind") != field or not doc.get("reviewer") or
                not doc.get("source_citation") or doc.get("value") != packet.get(field)):
            raise ValueError("reviewed occluder placement claim mismatch")
    validate_site(packet, CASES[case_key])
    return packet


def run_case(*, case_key: str, packet_path: Path, world, ego, route_reader,
             ray_reader, brake, camera_adapter, output: Path,
             control_factory=None, controller_gain: float = 1.0) -> dict:
    site = read_reviewed_site(packet_path, case_key=case_key, world=world)
    occluder = None
    started = False
    try:
        occluder = spawn_occluder(world, site, CASES[case_key])
        started = True
        camera_adapter.start()
        controller = (NativeSpeedController(CASES[case_key].target_mps, control_factory,
                                            controller_gain)
                      if control_factory is not None else None)
        return capture(case_key, site, world, ego, route_reader, ray_reader,
                       brake, output, camera_reader=camera_adapter.read,
                       before_tick=controller.apply if controller is not None else None)
    finally:
        try:
            if started:
                camera_adapter.stop()
        finally:
            if occluder is not None:
                occluder.destroy()


def run_case_with_reviewed_route(*, case_key: str, packet_path: Path, world,
                                 ego, ray_reader, brake, camera_adapter,
                                 output: Path, control_factory=None,
                                 traffic_reader=None, location_factory=None,
                                 controller_gain: float = 1.0) -> dict:
    """Bind an original body route reader to a separately cited route source.

    A reviewed arm geometry source can bind the supplied live ray reader or
    build the Native actor census and ray reader. Neither path manufactures
    sight evidence from the requested case label.
    """
    site = read_reviewed_site(packet_path, case_key=case_key, world=world)
    ref = site.get("source_files", {}).get("ego_route_geometry")
    if not isinstance(ref, dict):
        raise ValueError("reviewed route geometry source missing")
    name = ref.get("path")
    if (not isinstance(name, str) or not name or Path(name).is_absolute() or
            ".." in Path(name).parts or "\\" in name):
        raise ValueError("unsafe reviewed route source path")
    route_path = Path(packet_path).parent / name
    if any(part.is_symlink() for part in
           [Path(packet_path).parent.joinpath(*Path(name).parts[:i])
            for i in range(1, len(Path(name).parts) + 1)]):
        raise ValueError("symlinked reviewed route source path")
    if hashlib.sha256(route_path.read_bytes()).hexdigest() != ref.get("sha256"):
        raise ValueError("reviewed route source inventory hash mismatch")
    route_reader = ReviewedRouteReader(site, route_path)
    if ray_reader is None:
        ref = site.get("source_files", {}).get("arm_sight_geometry")
        if not isinstance(ref, dict) or not callable(location_factory):
            raise ValueError("reviewed arm geometry and Native location factory required")
        name = ref.get("path")
        if (not isinstance(name, str) or not name or Path(name).is_absolute() or
                ".." in Path(name).parts or "\\" in name):
            raise ValueError("unsafe reviewed arm geometry source path")
        ray_path = Path(packet_path).parent / name
        if any(part.is_symlink() for part in
               [Path(packet_path).parent.joinpath(*Path(name).parts[:i])
                for i in range(1, len(Path(name).parts) + 1)]):
            raise ValueError("symlinked reviewed arm geometry source path")
        if hashlib.sha256(ray_path.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("reviewed arm geometry inventory hash mismatch")
        ray_reader = ReviewedRayReader(site, ray_path, world, traffic_reader,
                                       location_factory, ego_id=getattr(ego, "id", None))
    return run_case(case_key=case_key, packet_path=packet_path, world=world,
                    ego=ego, route_reader=route_reader, ray_reader=ray_reader,
                    brake=brake, camera_adapter=camera_adapter, output=output,
                    control_factory=control_factory, controller_gain=controller_gain)
