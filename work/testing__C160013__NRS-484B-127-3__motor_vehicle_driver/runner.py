"""Exact Native caravan or motorcade spacing construction entry point."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from motorcade_spacing import CASES, execute_case, validate_source_packet

ROOT = Path(__file__).resolve().parent
AID = 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver'


def check(root=ROOT):
    config = json.loads((Path(root) / 'config.json').read_text())
    selected = config.get('selected_case_id')
    if (config.get('assignment_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (AID, 'NRS-484B-127-3', 'C160013',
                                     'motor_vehicle_driver'):
        raise ValueError('exact caravan/motorcade identity mismatch')
    if (config.get('rate_hz'), config.get('duration_s'), config.get('frame_count')) != (20, 30, 600):
        raise ValueError('original capture clock mismatch')
    if selected not in {AID + '__' + case.suffix for case in CASES}:
        raise ValueError('selected exact case missing')
    if set(config.get('supported_case_ids', [])) != {AID + '__' + case.suffix for case in CASES}:
        raise ValueError('exact case inventory mismatch')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('unsupported ontology or packet mapping')
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-packet', default=os.environ.get('C160013_REVIEWED_PACKET'))
    parser.add_argument('--adapter-module', default=os.environ.get('C160013_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default=os.environ.get('CARLA_HOST'))
    parser.add_argument('--port', type=int, default=os.environ.get('CARLA_PORT'))
    args = parser.parse_args()
    selected = check()
    if args.check:
        print('exact caravan/motorcade bundle passed: ' + selected)
        return
    if not all((args.reviewed_packet, args.adapter_module, args.output_dir,
                args.host, args.port)):
        raise ValueError('reviewed Native packet, adapter and endpoint required')
    packet_path = Path(args.reviewed_packet)
    if not packet_path.is_file() or packet_path.is_symlink():
        raise ValueError('reviewed Native packet file required')
    packet = json.loads(packet_path.read_text())
    case = next(item for item in CASES if selected == AID + '__' + item.suffix)
    validate_source_packet(packet, case)
    adapter_path = Path(args.adapter_module)
    if not adapter_path.is_file() or adapter_path.is_symlink():
        raise ValueError('reviewed Native adapter file required')
    adapter_binding = packet.get('native_adapter') or {}
    if (adapter_binding.get('sha256') != hashlib.sha256(adapter_path.read_bytes()).hexdigest()
            or not adapter_binding.get('reviewer') or not adapter_binding.get('citation')):
        raise ValueError('hash-bound reviewed Native adapter required')
    sources = packet.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('reviewed map, assets and legal context source inventory required')
    for source in sources:
        item = Path(source.get('path', ''))
        if (not item.is_file() or item.is_symlink() or not source.get('reviewer')
                or not source.get('citation')
                or source.get('sha256') != hashlib.sha256(item.read_bytes()).hexdigest()):
            raise ValueError('reviewed original source hash/citation mismatch')
    spec = importlib.util.spec_from_file_location('motorcade_native_adapter', adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError('Native adapter cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        config = json.loads((ROOT / 'config.json').read_text())
        execute_case(adapter, packet, case, config.get('engineering'))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        adapter.seal_original(args.output_dir)
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
