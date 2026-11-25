"""Exact reviewed-source Native capture entrypoint for C104084.

Run only after a reviewer supplies original source documents, a matching live
OpenDRIVE map and reviewed Native actor/camera setup. No fixture is accepted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from carla_delegate import CarlaDelegate
from canonical_bridge import bridge
from native_capture import capture
from native_source_adapter import ReviewedAdapter

ASSIGNMENT = 'testing__C104084__NRS-484B-213-2a__motor_vehicle_driver'


def run(client, packet_path, source_root, output, case_id, *, carla_module=None):
    output = Path(output)
    if not output.is_dir() or (output / 'original').exists():
        raise ValueError('fresh original child required in canonical attempt')
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if case_id != packet.get('case_id') or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('reviewed Native packet and exact case differ')
    original = output / 'original'
    original.mkdir()
    delegate = CarlaDelegate(client, packet, case_id, original,
                             carla_module=carla_module, graph_root=output)
    adapter = ReviewedAdapter(delegate, packet_path=packet_path,
                              source_root=Path(source_root), output=original,
                              world=client.get_world())
    result = capture(adapter, original, assignment_id=ASSIGNMENT, case_id=case_id,
                     graph_observer=adapter.graph_observer)
    release = delegate.release_receipt()
    if not release['world_restored'] or not release['actors_released'] or not release['sensors_released']:
        raise ValueError('Native owner release readback failed')
    (output / 'owner-release.json').write_text(json.dumps(release, indent=2,
                                                        sort_keys=True) + '\n', encoding='utf-8')
    published = bridge(output, original, assignment_id=ASSIGNMENT,
                       case_id=case_id, release=release)
    return {'original_capture': result, 'canonical_publication': published}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({'entrypoint': 'runner.py', 'exact_assignment': ASSIGNMENT,
                          'reviewed_source_required': True}, sort_keys=True))
        return
    if not args.host or args.port is None or args.output_dir is None:
        parser.error('--host, --port and --output-dir required')
    config = json.loads((args.output_dir / 'config.json').read_text())
    packet = Path(config['reviewed_packet'])
    source_root = Path(config['reviewed_source_root'])
    if not packet.is_absolute():
        packet = args.output_dir / packet
    if not source_root.is_absolute():
        source_root = args.output_dir / source_root
    case_id = config['selected_case_id']
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    result = run(client, packet, source_root, args.output_dir,
                 case_id, carla_module=carla)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
