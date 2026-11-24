"""Bind a reviewed C109749 scene to live tick acquisition and cleanup.

The scene factory must spawn from the reviewed request and register every owned
actor and sensor with the lease. It may not substitute a diagnostic map packet.
This module does not infer realized left-turn behavior from requested controls.
"""

import json
from pathlib import Path

from bundle_runner import check
from carla_live_adapter import CarlaTickAdapter, WorldLease
from native_acquisition import CAMERAS, capture


def run(*, client, config_path, map_path, output, scene_factory,
        location_factory, left_blinker_mask, frame_count=900):
    """Run one exact case under an owned synchronous Native world lease."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    packet = json.loads(Path(map_path).read_text(encoding="utf-8"))
    if packet.get("diagnostic_fixture") or packet.get("reviewed_original_map") is not True:
        raise ValueError("live capture requires reviewed original Native map packet")
    request = check(config, packet)
    if frame_count != request["capture"]["frame_count"]:
        raise ValueError("live recording must use exact 900-frame capture contract")
    world = client.get_world()
    if world is None:
        raise ValueError("live CARLA world unavailable")
    with WorldLease(world) as lease:
        scene = scene_factory(world=world, request=request, packet=packet, lease=lease)
        if not isinstance(scene, dict) or set(scene) != {
                "ego", "opponent", "cameras", "control_step"}:
            raise ValueError("live scene factory did not supply exact actor/camera/control set")
        if not callable(scene["control_step"]) or set(scene["cameras"]) != set(CAMERAS):
            raise ValueError("live scene lacks four cameras or controller")
        actors = [scene["ego"], scene["opponent"], *scene["cameras"].values()]
        if any(actor not in lease.owned for actor in actors) or len({id(actor) for actor in actors}) != 6:
            raise ValueError("live scene contains unowned or aliased actors")
        adapter = CarlaTickAdapter(
            world=world, packet=packet, ego=scene["ego"],
            opponent=scene["opponent"], cameras=scene["cameras"],
            control_step=scene["control_step"],
            location_factory=location_factory,
            left_blinker_mask=left_blinker_mask)
        files = capture(adapter=adapter, case_id=request["case_id"],
                        map_path=map_path, output=output, frame_count=frame_count)
        return {"case_id": request["case_id"], "files": files,
                "native_map_sha256": adapter.attestation["native_map_sha256"],
                "physical_acceptance": "unverified"}
