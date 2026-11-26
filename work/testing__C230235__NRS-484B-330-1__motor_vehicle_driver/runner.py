"""Exact C230235 original Native flagger capture; reviewed sources are mandatory."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'testing__C230235__NRS-484B-330-1__motor_vehicle_driver'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check():
    config = json.loads((HERE / 'config.json').read_text())
    if hashlib.sha256((HERE / 'case-plan.json').read_bytes()).hexdigest() != config['plan_sha256']:
        raise ValueError('exact selected flagger plan changed')
    cases = json.loads((HERE / 'case-plan.json').read_text())['cases']
    case = next((row for row in cases if row['case_id'] == config['selected_case_id']), None)
    if case is None or (config['assignment_id'], config['cell_id'], config['law_id'], config['actor']) != (
            ASSIGNMENT, 'C230235', 'NRS-484B-330-1', 'motor_vehicle_driver'):
        raise ValueError('exact selected flagger identity mismatch')
    if config['rate_hz'] != 20 or config['duration_s'] != 45 or config['capture_frames'] != 900:
        raise ValueError('selected 20 Hz 900-frame profile differs')
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    case = check()
    if args.check:
        print(case['case_id'])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError('Native host, port and output directory required')
    packet_path = os.environ.get('SCENARIO_FLAGGER_SOURCE_PACKET')
    packet_sha = os.environ.get('SCENARIO_FLAGGER_SOURCE_SHA256')
    operator_path = os.environ.get('SCENARIO_FLAGGER_OPERATOR_MODULE')
    operator_sha = os.environ.get('SCENARIO_FLAGGER_OPERATOR_SHA256')
    if not all((packet_path, packet_sha, operator_path, operator_sha)):
        raise ValueError('source-hashed reviewed flagger packet and Native operator required')
    packet_path, operator_path = Path(packet_path), Path(operator_path)
    if hashlib.sha256(packet_path.read_bytes()).hexdigest() != packet_sha:
        raise ValueError('reviewed flagger packet hash mismatch')
    if hashlib.sha256(operator_path.read_bytes()).hexdigest() != operator_sha:
        raise ValueError('reviewed Native operator hash mismatch')
    source = _load('c230235_source', HERE / 'source_packet.py')
    verified = source.verify(packet_path)
    if verified['case_id'] != case['case_id']:
        raise ValueError('reviewed source packet selects another exact case')
    packet = json.loads(packet_path.read_text())
    tuning = json.loads((HERE / 'candidate-tuning.json').read_text())
    camera_offset = tuning.get('camera_mount_offset_m')
    if type(camera_offset) not in (int, float) or camera_offset not in (0, 1.5):
        raise ValueError('reviewed camera mount offset differs from selected candidate')
    operator_module = _load('reviewed_flagger_operator', operator_path)
    if not callable(getattr(operator_module, 'make_operator', None)):
        raise ValueError('reviewed Native operator factory missing')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    scene = dict(packet['scene'], camera_mount_offset_m=camera_offset)
    operator = operator_module.make_operator(world, scene, case['case_id'])
    for method in ('map_bytes', 'snapshot_settings', 'configure_sync', 'readback_sync',
                   'spawn_flagger', 'spawn_vehicle', 'set_signal', 'set_route',
                   'spawn_cameras', 'tick_capture', 'destroy', 'actor_id',
                   'restore_settings', 'readback_restored'):
        if not callable(getattr(operator, method, None)):
            raise ValueError('reviewed Native operator callback missing: ' + method)
    if not callable(getattr(operator, 'camera_mount_offset_m', None)) or \
            operator.camera_mount_offset_m() != camera_offset:
        raise ValueError('selected camera mount offset not applied by Native operator')
    map_bytes = operator.map_bytes()
    if type(map_bytes) is not bytes or hashlib.sha256(map_bytes).hexdigest() != verified['source_hashes']['map_opendrive']:
        raise ValueError('loaded CARLA OpenDRIVE differs from reviewed source')
    acquire = _load('c230235_acquire', HERE / 'native_acquisition.py').acquire
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / 'original-flagger-source'
    sealed = acquire(operator, packet_path, source_dir)
    if sealed['source_frame_count'] != 900 or sealed['source_kind'] != 'original_reviewed':
        raise ValueError('original full flagger capture incomplete')
    bridge = _load('c230235_bridge', HERE / 'native_output_bridge.py')
    bridge.publish(output, source_dir=source_dir, map_bytes=map_bytes, restored=True)
    print(json.dumps({'case_id': case['case_id'], 'source_frame_count': 900}, sort_keys=True))


if __name__ == '__main__':
    main()
