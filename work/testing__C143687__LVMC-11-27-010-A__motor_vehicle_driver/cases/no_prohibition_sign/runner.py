"""Exact trail construction preflight; Native acquisition remains source gated."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from source_packet import verify_packet
from trail import CASES, build_case


class DiagnosticAdapter:
    """Records construction calls without creating CARLA actors."""

    def __init__(self):
        self.calls = []

    def install_sign(self, position, text, **kwargs):
        self.calls.append(('install_sign', position, text, kwargs))
        return 'diagnostic-sign'

    def spawn_vehicle(self, position, blueprint, **kwargs):
        self.calls.append(('spawn_vehicle', position, blueprint, kwargs))
        return 'diagnostic-vehicle'

    def set_route(self, vehicle, route, **kwargs):
        self.calls.append(('set_route', vehicle, route, kwargs))

    def bind_status(self, vehicle, **kwargs):
        self.calls.append(('bind_status', vehicle, kwargs))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def check_bundle(root: Path) -> dict:
    root = Path(root).resolve()
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    site = json.loads((root / 'site.json').read_text(encoding='utf-8'))
    if config.get('cell_id') != 'C143687' or config.get('actor') != 'motor_vehicle_driver':
        raise ValueError('exact trail assignment identity mismatch')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('exact trail capture clock mismatch')
    if tuple(camera['name'] for camera in config.get('cameras', [])) != ('overview', 'approach', 'reference_corner', 'driver_reference'):
        raise ValueError('exact four-camera plan missing')
    suffix = config.get('selected_case_id', '').rsplit('__', 1)[-1]
    case = next((item for item in CASES if item.name == suffix), None)
    if case is None or config['selected_case_id'] != (
            'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver__' + suffix):
        raise ValueError('unknown exact trail case')
    if site.get('case_id') != config['selected_case_id']:
        raise ValueError('site and selected case differ')
    source = verify_packet(site, root / 'packet.json')
    adapter = DiagnosticAdapter()
    result = build_case(adapter, site, case)
    if [call[0] for call in adapter.calls] != [
            'install_sign', 'spawn_vehicle', 'set_route', 'bind_status']:
        raise ValueError('trail construction call sequence incomplete')
    return {'case_id': config['selected_case_id'], 'source_packet_sha256': source['packet_sha256'],
            'source_count': len(source['source_sha256']), 'construction_calls': len(adapter.calls),
            'diagnostic_fixture': site.get('provenance_kind') == 'diagnostic_fixture',
            'native_started': False, 'physical_claimed': False,
            'legal_judgment': None, 'owned_resources': list(result['owned'])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    result = check_bundle(Path(__file__).resolve().parent)
    if not args.check:
        raise ValueError('Native four-camera acquisition and reviewed original site are not bound')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
