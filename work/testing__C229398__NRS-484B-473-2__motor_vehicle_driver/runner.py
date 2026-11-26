"""Lazy original Native parked-lamp entrypoint; reviewed sources gate CARLA use."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from parked_lamps import CASES
from source_packet import ASSIGNMENT, verify

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / 'config.json').read_text())
    if config.get('assignment_id') != ASSIGNMENT or config.get('law_id') != 'NRS-484B-473-2' or config.get('cell_id') != 'C229398':
        raise ValueError('exact parked-lamp bundle scope changed')
    if hashlib.sha256((HERE / 'case-plan.json').read_bytes()).hexdigest() != config.get('plan_sha256'):
        raise ValueError('exact parked-lamp plan changed')
    case = next((item for item in CASES if config.get('selected_case_id') == ASSIGNMENT + '__' + item.name), None)
    if case is None or config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('selected case or capture profile differs')
    return config, case


def _reviewed_file(path_string, digest, description):
    if not path_string or not digest:
        raise ValueError('source-hashed reviewed parked-light ' + description + ' required')
    path = Path(path_string).resolve()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('reviewed parked-light ' + description + ' bytes changed')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config, case = check()
    if args.check:
        print(config['selected_case_id'])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError('Native host, port and output directory required')
    packet_path = _reviewed_file(os.environ.get('SCENARIO_PARKED_LIGHT_SOURCE_PACKET'),
                                 os.environ.get('SCENARIO_PARKED_LIGHT_SOURCE_SHA256'), 'site packet')
    checked = verify(packet_path)
    if checked['case_id'] != config['selected_case_id']:
        raise ValueError('reviewed packet selects another exact case')
    operator_path = _reviewed_file(os.environ.get('SCENARIO_PARKED_LIGHT_OPERATOR_MODULE'),
                                   os.environ.get('SCENARIO_PARKED_LIGHT_OPERATOR_SHA256'), 'operator')
    spec = importlib.util.spec_from_file_location('reviewed_parked_light_operator', operator_path)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed Native operator cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'make_adapter', None)):
        raise ValueError('reviewed Native operator factory missing')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    packet = json.loads(packet_path.read_text())
    adapter = module.make_adapter(client.get_world(), packet['scene'], case.name,
                                  approach_offset_m=config['approach_offset_m'])
    from native_acquisition import acquire
    receipt = acquire(adapter, packet_path, args.output_dir)
    from native_output_bridge import publish
    publish(args.output_dir, restored=True)
    print(json.dumps({'case_id': receipt['case_id'], 'original_frames': receipt['source_frame_count']}))


if __name__ == '__main__':
    main()
