"""Exact red-curb Native entry point; CARLA is loaded only by a reviewed adapter."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

from red_curb import CASES
from source_packet import ASSIGNMENT, checked_adapter, load_reviewed

ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    config = json.loads((Path(root) / 'config.json').read_text(encoding='utf-8'))
    if (config.get('assignment_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            ASSIGNMENT, 'LVMC-11-52-030-A', 'C229452', 'motor_vehicle_driver'):
        raise ValueError('exact red-curb assignment identity differs')
    if config.get('selected_case_id') not in {
            ASSIGNMENT + '__' + case.name for case in CASES}:
        raise ValueError('exact red-curb case missing')
    if (config.get('rate_hz'), config.get('duration_s'),
            config.get('frame_count')) != (20, 1806, 36120):
        raise ValueError('original 1806-second capture clock differs')
    if [cam.get('name') for cam in config.get('cameras', [])] != [
            'overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('four original camera views required')
    if config.get('candidate_id') not in ('primary', 'fallback1'):
        raise ValueError('unknown red-curb construction candidate')
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-packet', default=os.environ.get('C229452_REVIEWED_PACKET'))
    parser.add_argument('--adapter-module', default=os.environ.get('C229452_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--host', default=os.environ.get('CARLA_HOST'))
    parser.add_argument('--port', type=int, default=os.environ.get('CARLA_PORT'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'))
    args = parser.parse_args()
    config = check()
    if args.candidate is not None and args.candidate != config['candidate_id']:
        raise ValueError('candidate differs from immutable bundle')
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'], 'simulation_started': False}))
        return
    if not all((args.reviewed_packet, args.adapter_module, args.host,
                args.port, args.output_dir)):
        raise ValueError('reviewed source packet, Native adapter and endpoint required')
    packet, _, _ = load_reviewed(args.reviewed_packet, config['selected_case_id'])
    module_path = checked_adapter(args.adapter_module, packet)
    spec = importlib.util.spec_from_file_location('reviewed_red_curb_adapter', module_path)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed Native adapter cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    from native_capture import acquire
    try:
        result = acquire(adapter, args.reviewed_packet,
                         config['selected_case_id'], args.output_dir,
                         adapter_module_path=module_path,
                         candidate=config['candidate_id'])
        print(json.dumps(result, sort_keys=True))
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
