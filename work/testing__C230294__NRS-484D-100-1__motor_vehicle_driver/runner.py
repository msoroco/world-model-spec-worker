"""Lazy exact-case lamp construction entrypoint; no CARLA use in --check."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from lamp_direction import CASES
from source_packet import ASSIGNMENT, verify

ROOT = Path(__file__).resolve().parent


def check():
    config = json.loads((ROOT / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    if config.get('assignment_id') != ASSIGNMENT or config.get('law_id') != 'NRS-484D-100-1' or config.get('cell_id') != 'C230294':
        raise ValueError('lamp bundle identity mismatch')
    if case_id not in {ASSIGNMENT + '__' + case.name for case in CASES}:
        raise ValueError('unknown selected lamp case')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('lamp capture cadence mismatch')
    if [view.get('name') for view in config.get('cameras', [])] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('four-camera lamp profile missing')
    return config


def checked_file(path_text, sha256, description):
    if not path_text or not sha256:
        raise ValueError('reviewed lamp ' + description + ' required')
    path = Path(path_text).resolve()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise ValueError('reviewed lamp ' + description + ' bytes changed')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = check()
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'], 'simulation_started': False}))
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError('Native host, port and output directory required')
    packet_path = checked_file(os.environ.get('SCENARIO_LAMP_SOURCE_PACKET'),
                               os.environ.get('SCENARIO_LAMP_SOURCE_SHA256'), 'site packet')
    case_name = config['selected_case_id'].removeprefix(ASSIGNMENT + '__')
    checked = verify(packet_path, case_name)
    operator_path = checked_file(os.environ.get('SCENARIO_LAMP_OPERATOR_MODULE'),
                                 os.environ.get('SCENARIO_LAMP_OPERATOR_SHA256'), 'Native operator')
    spec = importlib.util.spec_from_file_location('reviewed_lamp_operator', operator_path)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed lamp Native operator cannot load')
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    if not callable(getattr(operator, 'make_adapter', None)):
        raise ValueError('reviewed lamp Native adapter factory missing')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    from native_acquisition import acquire
    adapter = operator.make_adapter(client.get_world(), checked['packet']['scene'],
                                    case_name, config)
    result = acquire(adapter, packet_path, args.output_dir)
    print(json.dumps({'case_id': config['selected_case_id'],
                      'original_frames': result['frame_count'],
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
