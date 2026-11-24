"""C144550 original-source Native lane-change capture entrypoint.

The CPU check validates the exact configuration without importing CARLA.
Native execution requires a fresh runtime.py materialized attempt.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from native_lane_construction import (
    CAMERA_SIZES, CASE_PREFIX, SIGNAL_CASES, FFV1CameraWriter,
    camera_transforms_for_site, capture_native_case, find_native_lane_site,
    make_native_lane_context, make_original_observer, source_cameras,
    stage_native_lane_case,
)


def validate_config(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-223-1b", "C144550", "motor_vehicle_driver"):
        raise ValueError("Wrong C144550 assignment identity")
    expected=[CASE_PREFIX+suffix for suffix in SIGNAL_CASES]
    supported=config.get("supported_case_ids")
    if config.get("selected_case_id") not in expected or not isinstance(supported,list) or not set(expected)<=set(supported):
        raise ValueError("Selected C144550 case IDs required")
    if (config.get("rate_hz"),config.get("duration_s"))!=(20,45):
        raise ValueError("Exact C144550 duration and rate required")
    cameras=config.get("cameras")
    if not isinstance(cameras,list) or [c.get("name") for c in cameras]!=list(CAMERA_SIZES):
        raise ValueError("Four named original cameras required")
    if any((c.get("width"),c.get("height"),c.get("fov_deg")) !=
           (*CAMERA_SIZES[c["name"]],90) for c in cameras):
        raise ValueError("Original camera profile differs")
    if not isinstance(config.get("required_atoms"),list) or not isinstance(config.get("source_packets"),list):
        raise ValueError("Source observation contract required")
    for name,minimum,maximum in (("target_initial_route_distance_m",10,250),
                                  ("target_speed_mps",2,10),
                                  ("overview_along_m",30,100)):
        value=config.get(name)
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value)
                                  or not minimum<=value<=maximum):
            raise ValueError("Invalid construction knob: "+name)
    return config


def capture(args,config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output=Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/"construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize the exact construction")
    client=carla.Client(args.host,args.port)
    client.set_timeout(30)
    saved=snapshot(client)
    writers={}
    frames=0
    succeeded=False
    try:
        world=client.get_world()
        settings=world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        case_id=config["selected_case_id"]
        suffix=case_id[len(CASE_PREFIX):]
        direction=SIGNAL_CASES[suffix][0]
        site=find_native_lane_site(world,direction,carla.LaneType.Driving,
                                   config["physical_completion"]["destination_lane"])
        blueprints=sorted(world.get_blueprint_library().filter("vehicle.*"),key=lambda item:item.id)
        if not blueprints:raise ValueError("No Native motor-vehicle blueprint")
        with stage_native_lane_case(world,site,case_id,blueprints[0],
                                    config.get("target_initial_route_distance_m")) as actors:
            ego=actors["ego"]
            target_initial_distance=actors["target_initial_route_distance_m"]
            with (output/"lane_context.json").open("x") as stream:
                stream.write(json.dumps(make_native_lane_context(
                    world,site["selected"],site["source_polygon"]),
                    indent=2,allow_nan=False)+"\n")
            observer=make_original_observer(world,ego,site["selected"],
                                            carla.VehicleLightState,site["source_polygon"])
            transforms=camera_transforms_for_site(carla,site,
                                                  config.get("overview_along_m",65))
            with source_cameras(world,ego,transforms) as cameras:
                frame_map=None;history=None;helper=None
                try:
                    for name,(width,height) in CAMERA_SIZES.items():
                        writers[name]=FFV1CameraWriter(output/(name+".mkv"),width,height)
                    frame_map=FrameMap(output/"video_frames.jsonl")
                    history=(output/"lane_history.jsonl").open("x",buffering=1)
                    helper=PipelineCapture(client,ego,output,case_id,
                                           required_observations=config["required_atoms"])
                    rows=capture_native_case(
                        world,ego,site["selected"],case_id,carla.VehicleLightState,
                        carla.VehicleControl,observer,cameras,writers,frame_map,history,
                        lambda frame,time_s:helper.capture(frame,time_s),
                        target_speed_mps=config.get("target_speed_mps",5.0))
                    frames=len(rows)
                    succeeded=True
                finally:
                    original_failure=sys.exc_info()[0] is not None
                    close_errors=[]
                    resources=([helper] if helper is not None else [])+list(writers.values())
                    resources+=([frame_map] if frame_map is not None else [])
                    resources+=([history] if history is not None else [])
                    for resource in resources:
                        try:
                            if resource is helper:helper.close(confirmed=succeeded)
                            else:resource.close()
                        except Exception as error:close_errors.append(str(error))
                    if close_errors and not original_failure:
                        raise ValueError("Native source closure failed: "+"; ".join(close_errors))
    finally:
        restoration=restore(client,saved)
    if succeeded:
        seal_capture(output,frames=frames,restoration=restoration,errors=[],
                     encoder_exit_codes={name:writer.exit_code for name,writer in writers.items()},
                     context={"selected_case_id":config["selected_case_id"],
                              "native_site_candidate_count":site["candidate_count"],
                              "target_initial_route_distance_m":target_initial_distance,
                              "actual_marking_signal_gap_review_pending":True,
                              "legal_safety_ascertainment":"unresolved"})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=2000)
    parser.add_argument("--output-dir")
    args=parser.parse_args()
    config=validate_config(json.loads(Path("config.json").read_text()))
    if args.check:
        print(json.dumps({"case_id":config["selected_case_id"],"cpu_check_passed":True,
                          "simulation_started":False}))
        return
    if not args.output_dir:raise ValueError("Fresh runtime.py output directory required")
    capture(args,config)


if __name__=="__main__":main()
