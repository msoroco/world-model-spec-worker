"""Offline exact-case preflight for the 400(2)(a) approach package."""
import argparse
import json
import os
import shutil
import tempfile
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
    adapter = NativeCarlaAdapter(world, carla_module, packet, config, client=client)
    return run_capture(adapter, config, map_packet, output)


def run_native_publication(config, map_packet, output, host, port,
                           *, carla_module=None):
    """Capture originals, publish Core/media, and seal after verified cleanup."""
    from native_core import project
    from worker_exchange.native_output import seal_capture

    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('existing materialized Native output required')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Native publication scratch must be under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='c109705-native-', dir=scratch))
    try:
        original = stage / 'original'
        run = run_native_source(config, map_packet, original, host, port,
                                carla_module=carla_module)
        if run.get('restoration_verified') is not True:
            raise ValueError('Native world restoration not verified')
        acquisition = json.loads((original / 'acquisition.json').read_text())
        if acquisition.get('diagnostic_fixture') is not False:
            raise ValueError('diagnostic source cannot publish Native closure')
        core = stage / 'core'
        receipt = project(original, core)
        for source_root in (original, core):
            for source in source_root.iterdir():
                target = output / source.name
                if target.exists():
                    if (source.is_file() and target.is_file() and
                            source.read_bytes() == target.read_bytes()):
                        continue
                    raise ValueError('Native publication target already exists: '
                                     + source.name)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'original_acquisition_sha256': __import__('hashlib').sha256(
                (output / 'acquisition.json').read_bytes()).hexdigest(),
            'core_receipt_sha256': __import__('hashlib').sha256(
                (output / 'receipt.json').read_bytes()).hexdigest()}, indent=2) + '\n')
        seal = seal_capture(output, frames=run['frame_count'],
                            restoration={'restored': True,
                                         'method': 'NativeCarlaAdapter.cleanup settings and actor release'},
                            errors=[], encoder_exit_codes={name: 0 for name in
                                receipt['media']['encoded_camera_sha256']},
                            context=acquisition['map_binding'])
        return {'case_id': config['selected_case_id'],
                'source_frames': run['frame_count'],
                'capture_seal_format': seal['format'],
                'physical_acceptance_claimed': False}
    except BaseException as error:
        (output / 'native-run-status.json').write_text(json.dumps({
            'errors': [type(error).__name__ + ': ' + str(error)],
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)

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
        packet = args.map_packet or os.environ.get('CARLA_MAP_PACKET')
        if not packet:
            raise ValueError('source-hashed CARLA_MAP_PACKET required')
        if not args.output_dir:
            raise ValueError('materialized Native output required')
        print(json.dumps(run_native_publication(config, packet, args.output_dir,
                                               args.host or '127.0.0.1',
                                               args.port or 2000)))

if __name__=="__main__":
    main()
