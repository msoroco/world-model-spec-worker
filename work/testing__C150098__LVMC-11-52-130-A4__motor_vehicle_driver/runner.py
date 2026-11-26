"""Exact hydrant bundle entry point; original sources are required locally."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

from hydrant import ASSIGNMENT, CASES
from native_packet import validate_packet
from native_runner import capture_original, sha

ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    cases = {ASSIGNMENT + '__' + case.suffix: case for case in CASES}
    if case_id not in cases:
        raise ValueError('selected exact hydrant case absent')
    case = cases[case_id]
    if ((config.get('assignment_id'), config.get('law_id'), config.get('cell_id'),
         config.get('actor')) != (ASSIGNMENT, 'LVMC-11-52-130-A4', 'C150098',
                                  'motor_vehicle_driver')):
        raise ValueError('exact hydrant assignment identity differs')
    if (config.get('rate_hz'), config.get('duration_s'), config.get('frame_count')) != (20, 45, 900):
        raise ValueError('exact hydrant capture clock differs')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('original observation packets must remain explicit')
    if (config.get('requested_side'), config.get('requested_gap_m'),
        config.get('requested_activity'), config.get('requested_exception')) != (
            case.side, case.gap_m, case.activity, case.exception):
        raise ValueError('exact hydrant construction differs')
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-packet', default=os.environ.get('C150098_REVIEWED_PACKET'))
    parser.add_argument('--adapter-module', default=os.environ.get('C150098_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default=os.environ.get('CARLA_HOST'))
    parser.add_argument('--port', type=int, default=os.environ.get('CARLA_PORT'))
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print('exact hydrant bundle passed: ' + case_id)
        return
    if not all((args.reviewed_packet, args.adapter_module, args.output_dir,
                args.host, args.port)):
        raise ValueError('reviewed original packet, Native adapter and endpoint required')
    validate_packet(args.reviewed_packet, case_id)
    packet = json.loads(Path(args.reviewed_packet).read_text(encoding='utf-8'))
    module_path = Path(args.adapter_module)
    binding = packet.get('native_adapter')
    if (not module_path.is_file() or module_path.is_symlink() or
            not isinstance(binding, dict) or binding.get('sha256') != sha(module_path) or
            not binding.get('citation') or not binding.get('reviewer')):
        raise ValueError('hash-bound original Native adapter required')
    spec = importlib.util.spec_from_file_location('hydrant_native_adapter', module_path)
    if spec is None or spec.loader is None:
        raise ValueError('original Native adapter module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        print(capture_original(adapter, args.reviewed_packet, case_id, args.output_dir,
                               adapter_module_path=module_path))
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
