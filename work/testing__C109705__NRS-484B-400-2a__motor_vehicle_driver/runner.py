"""Offline exact-case preflight for the 400(2)(a) approach package."""
import argparse
import json
import os
from pathlib import Path

PREFIX = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__"

def check(config):
    case = config.get("selected_case_id", "")
    suffix = case.removeprefix(PREFIX)
    if not case.startswith(PREFIX) or suffix not in (
            "near_centerline", "farther_from_centerline",
            "imaginary_near_centerline", "imaginary_farther_from_centerline"):
        raise ValueError("wrong exact case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-400-2a", "C109705", "motor_vehicle_driver"):
        raise ValueError("wrong frozen law/cell/actor")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("wrong timing contract")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or [c.get("name") for c in cameras if isinstance(c, dict)] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four camera plan missing")
    if [(c.get("width"), c.get("height")) for c in cameras] != [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError("four camera dimensions differ")
    if any(not c.get("pose_strategy") or not c.get("fov_deg") for c in cameras):
        raise ValueError("four camera geometry missing")
    kind = "imaginary_equidistant" if suffix.startswith("imaginary_") else "marked"
    if config.get("centerline_kind") != kind:
        raise ValueError("centerline construction mismatch")
    target = 2.7 if "farther" in suffix else 1.7
    if config.get("target_approach_offset_m") != target:
        raise ValueError("approach position target mismatch")
    return {"case_id": case, "offline_contract_passed": True,
            "native_map_survey_required": True, "physical_realization": "pending"}


def run_capture(adapter, config, map_packet, output):
    """Execute a reviewed exact case with an injected Native CARLA adapter."""
    selected = check(config)['case_id']
    from native_capture import capture
    return capture(adapter, selected, Path(map_packet), Path(output))


def run_native_source(config, map_packet, output, host, port, *, carla_module=None):
    """Acquire an original, source-bound Native attempt with a dedicated server.

    The output is a new original-source directory. Runtime capture materializes
    an existing bundle and needs a separate Core publication step before its
    native closure seal can be issued.
    """
    check(config)
    if Path(output).exists():
        raise ValueError('Native source output already exists')
    if carla_module is None:
        import carla as carla_module
    from carla_adapter import NativeCarlaAdapter
    client = carla_module.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    packet = json.loads(Path(map_packet).read_text())
    adapter = NativeCarlaAdapter(world, carla_module, packet, config)
    return run_capture(adapter, config, map_packet, output)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--map-packet")
    parser.add_argument("--native-source-output")
    args=parser.parse_args()
    config=json.loads(Path("config.json").read_text())
    result=check(config)
    if args.check:
        print(json.dumps(result))
    elif args.native_source_output:
        packet = args.map_packet or os.environ.get('CARLA_MAP_PACKET')
        if not packet:
            raise ValueError('source-hashed CARLA_MAP_PACKET required')
        print(json.dumps(run_native_source(config, packet, args.native_source_output,
                                           args.host or '127.0.0.1', args.port or 2000)))
    else:
        raise RuntimeError('Native Core publication and closure seal unfinished for '
                           + result['case_id'])

if __name__=="__main__":
    main()
