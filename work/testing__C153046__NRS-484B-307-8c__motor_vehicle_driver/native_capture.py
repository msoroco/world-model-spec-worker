"""Wire source-bound Native actors, observations and original media capture."""
from __future__ import annotations

from pathlib import Path

from native_camera import CameraRig
from native_media import finalize
from native_runner import run_carla_with_plan
from native_routes import Routes
from native_setup import create


def capture(world, packet_path: Path, suffix: str, output_dir: Path,
            transform_factory, control_factory, walker_control, vector_factory,
            *, count: int = 600) -> dict:
    """Run one reviewed site; retain every original attempt even on failure."""
    output_dir = Path(output_dir).resolve()
    if count != 600:
        raise ValueError("exact 30-second 20 Hz capture requires 600 Native ticks")
    if any((output_dir / name).exists() for name in
           ("trace.jsonl", "raw", "overview.mkv", "approach.mkv",
            "reference_corner.mkv", "driver_reference.mkv")):
        raise ValueError("retain previous original Native attempt")
    output_dir.mkdir(parents=True, exist_ok=True)
    actors = create(world, packet_path, suffix, transform_factory)
    try:
        routes = Routes(packet_path, suffix, actors, control_factory,
                        walker_control, vector_factory)
        rig = CameraRig(world, actors.ego, packet_path, suffix,
                        output_dir / "raw", transform_factory)
        try:
            trace = run_carla_with_plan(world, actors.ego, actors.signal,
                                        actors.pedestrians, actors.traffic,
                                        packet_path=packet_path, case_suffix=suffix,
                                        output_path=output_dir / "trace.jsonl", count=count,
                                        control_factory=control_factory, camera_rig=rig,
                                        before_tick=routes.before_tick)
        finally:
            rig.close()
    finally:
        actors.close()
    media = finalize(output_dir / "trace.jsonl", output_dir / "raw", output_dir)
    return {"trace": trace, "media": media,
            "physical_acceptance_claimed": False}
