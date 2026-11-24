"""Run one source-bound 20 Hz Native crosswalk acquisition attempt.

The saved trace and four videos are original observations. This function does
not claim that the intended pass, stop, crossing or camera visibility occurred.
"""

from __future__ import annotations

import json
from pathlib import Path

from native_crosswalk_actors import NativeCrosswalkActors
from native_crosswalk_capture import NativeCrosswalkRecorder, FRAME_COUNT
from native_crosswalk_media import NativeCrosswalkCameras
from native_crosswalk_world import run_sourced_world


def _context(proposal: dict, site: dict, actor_ids: dict) -> dict:
    inventory = proposal["source_inventory"]
    if site.get("junction_kind") != "road_intersection" or site.get("alley_junction") is not False:
        raise ValueError("source-reviewed road intersection required")
    axis = site.get("road_axis")
    if not isinstance(axis, dict) or set(axis) != {"origin", "forward"}:
        raise ValueError("original road axis required")
    crossing = {"kind": proposal["crosswalk_kind"], "polygon": proposal["crosswalk_polygon"]}
    if proposal["crosswalk_kind"] == "unmarked":
        crossing["opposite_sidewalk_lateral_lines"] = site["opposite_sidewalk_lateral_lines"]
        crossing["curb_or_traveled_edge_sources"] = [inventory["curb_or_edge"]["citation"]]
    else:
        crossing["marking_source"] = inventory["marking"]["citation"]
    return {"case_id": proposal["case_id"], "map_sha256": inventory["map"]["sha256"],
            "map_id": proposal["map_id"], "layout": "intersection", "junction_kind": "road_intersection",
            "crosswalk": crossing, "stopped_vehicle_purpose": {
                "claim": proposal["lead_stop_purpose"],
                "source_ref": inventory["stopped_purpose"]["citation"]},
            "road_axis": axis, "ego_vehicle_identity": actor_ids["ego"],
            "lead_vehicle_identity": actor_ids["lead"], "pedestrian_identity": actor_ids["pedestrian"],
            "source_inventory": inventory, "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


def capture_case(*, world, carla, proposal: dict, output: str | Path) -> dict:
    """Capture original actors/cameras under the verified, restored world session."""
    root = Path(output)
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("fresh empty original capture directory required")
    source = Path(proposal["source"]["path"])
    site = json.loads(source.read_bytes())

    def acquire(active_world):
        actors = None
        cameras = None
        try:
            actors = NativeCrosswalkActors(world=active_world, carla=carla, proposal=proposal)
            context = _context(proposal, site, actors.actor_ids)
            recorder = NativeCrosswalkRecorder(case_id=proposal["case_id"], context=context,
                                               actor_ids=actors.actor_ids)
            cameras = NativeCrosswalkCameras(world=active_world, carla=carla, site=site, output=root)
            for _ in range(FRAME_COUNT):
                actors.control()
                frame = active_world.tick()
                images = cameras.append(frame)
                recorder.append(world_frame=frame, actors=actors.observe(frame), camera_frames=images)
            cameras.close(require_complete=True)
            cameras = None
            receipt = recorder.write(root)
            return {"receipt": receipt, "actor_ids": actors.actor_ids,
                    "video_paths": {name: str(root / (name + ".mkv")) for name in
                                    ("overview", "approach", "reference_corner", "driver_reference")}}
        finally:
            if cameras is not None:
                cameras.close(require_complete=False)
            if actors is not None:
                actors.close()

    return run_sourced_world(world=world, proposal=proposal, capture=acquire)
