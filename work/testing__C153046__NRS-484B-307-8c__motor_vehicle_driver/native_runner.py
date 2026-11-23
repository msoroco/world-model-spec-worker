"""Source-bound control and original-sample capture for the exact red-left cases.

The caller supplies a CARLA world, actor, and observation source. This module
does not manufacture signal, roadway, conflict, or motion observations.
"""
from __future__ import annotations

import json
from pathlib import Path

from red_left_turn_controller import Observation, controller_for_case
from native_frame import capture_frames, verify_live_site
from source_bound_scene import build as bind_scene


def run(actor, observations, *, packet_path: Path, case_suffix: str,
        control_factory, output_path: Path, original_evidence=None) -> dict:
    scene = bind_scene(Path(packet_path), case_suffix)
    controller = controller_for_case(case_suffix)
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError("retain the previous original trace; choose a new output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("x", encoding="utf-8") as stream:
        for observation in observations:
            if not isinstance(observation, Observation):
                raise ValueError("original Observation required")
            row = controller.step(observation)
            native_frame = original_evidence(observation) if original_evidence else None
            if native_frame is not None and native_frame.get("origin") != "native_world_snapshot":
                raise ValueError("original evidence must come from a Native world snapshot")
            request = row["control_request"]
            control = control_factory(**request)
            actor.apply_control(control)
            sample = {"case_id": scene["case_id"], "source_packet_sha256": scene["source_packet_sha256"],
                      "selected_approach_lane_id": scene["selected_approach_lane_id"],
                      "time_s": observation.time_s,
                      "distance_to_stop_boundary_m": observation.distance_to_stop_boundary_m,
                      "speed_m_s": observation.speed_m_s, "signal": observation.signal,
                      "pedestrian_conflict": observation.pedestrian_conflict,
                      "traffic_conflict": observation.traffic_conflict,
                      "junction_exited": observation.junction_exited,
                      "requested_phase": row["phase"], "control_request": request,
                      "original_sample_claim": native_frame is not None,
                      "frame": native_frame["frame"] if native_frame is not None else None,
                      "native_frame": native_frame, "physical_realization_claimed": False}
            if native_frame is not None:
                ego = native_frame["ego"]
                position = ego["location_xyz_m"]
                sample["position"] = {"x": position[0], "y": position[1], "z": position[2]}
                sample["heading_deg"] = ego["heading_deg"]
                sample["speed_mps"] = observation.speed_m_s
            stream.write(json.dumps(sample, sort_keys=True) + "\n")
            count += 1
    if count == 0:
        output_path.unlink()
        raise ValueError("original observation stream is empty")
    return {"case_id": scene["case_id"], "samples": count,
            "trace": str(output_path), "source_packet_sha256": scene["source_packet_sha256"],
            "physical_realization_claimed": False}


def run_carla(world, ego, signal_actor, pedestrians, traffic, *, packet_path: Path,
              case_suffix: str, output_path: Path, count: int, observation_from_frame,
              control_factory=None, camera_rig=None, before_tick=None) -> dict:
    """Tick Native world, capture full bodies, then request case control."""
    scene = verify_live_site(world, packet_path, case_suffix, signal_actor)
    if control_factory is None:
        import carla
        control_factory = carla.VehicleControl
    latest = {}

    def observations():
        for frame in capture_frames(world, ego, signal_actor, pedestrians, traffic,
                                    count=count, before_tick=before_tick):
            if camera_rig is not None:
                if (camera_rig.scene["source_packet_sha256"] != scene["source_packet_sha256"] or
                        camera_rig.scene["case_id"] != scene["case_id"]):
                    raise ValueError("camera rig uses another reviewed site packet")
                frame["original_cameras"] = camera_rig.await_frame(frame["frame"], frame["time_s"])
            latest["frame"] = frame
            observation = observation_from_frame(frame, scene)
            if not isinstance(observation, Observation):
                raise ValueError("original observation adapter returned no Observation")
            observed_red = frame["signal_state"].rsplit(".", 1)[-1].lower() == "red"
            if (observation.signal == "steady_red_alone") != observed_red:
                raise ValueError("controller signal observation differs from original Native signal state")
            yield observation

    return run(ego, observations(), packet_path=packet_path, case_suffix=case_suffix,
               control_factory=control_factory, output_path=output_path,
               original_evidence=lambda _: latest["frame"])


def run_carla_with_plan(world, ego, signal_actor, pedestrians, traffic, *, packet_path: Path,
                        case_suffix: str, output_path: Path, count: int,
                        control_factory=None, camera_rig=None, before_tick=None) -> dict:
    """Use reviewed conflict geometry to adapt each original Native frame."""
    from native_observation import plan, from_frame
    scene, observation_plan = plan(packet_path, case_suffix)

    def observe(frame, live_scene):
        if live_scene["source_packet_sha256"] != scene["source_packet_sha256"]:
            raise ValueError("reviewed observation plan differs from live site")
        return from_frame(frame, live_scene, observation_plan)

    return run_carla(world, ego, signal_actor, pedestrians, traffic,
                     packet_path=packet_path, case_suffix=case_suffix,
                     output_path=output_path, count=count,
                     observation_from_frame=observe, control_factory=control_factory,
                     camera_rig=camera_rig, before_tick=before_tick)
