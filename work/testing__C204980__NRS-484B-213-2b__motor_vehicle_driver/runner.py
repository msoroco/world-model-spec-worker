"""Source-gated Native runner for C204980 railroad crossing cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from carla_rail_adapter import CarlaRailAdapter
from canonical_bridge import bridge
from rail_capture import capture

ASSIGNMENT = 'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver'


def run(client, packet_path, source_root, output, case_id, *, carla_module=None):
    output = Path(output)
    if not output.is_dir() or (output / 'original').exists():
        raise ValueError('fresh canonical attempt without original child required')
    packet = json.loads(Path(packet_path).read_text())
    if case_id != packet.get('case_id') or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('reviewed railroad packet and case differ')
    original = output / 'original'
    original.mkdir()
    adapter = CarlaRailAdapter(client, packet, case_id, original,
                               carla_module=carla_module, graph_root=output)
    result = capture(adapter, packet_path, source_root, original, case_id)
    release = adapter.release_receipt()
    (output / 'owner-release.json').write_text(json.dumps(release, sort_keys=True) + '\n')
    published = bridge(output, original, assignment_id=ASSIGNMENT,
                       case_id=case_id, release=release)
    return {'original_capture': result, 'owner_release': release,
            'canonical_publication': published,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({'entrypoint': 'runner.py', 'assignment_id': ASSIGNMENT,
                          'reviewed_original_sources_required': True}, sort_keys=True))
        return
    if not args.host or args.port is None or args.output_dir is None:
        parser.error('--host, --port and --output-dir required')
    config = json.loads((args.output_dir / 'config.json').read_text())
    if config.get('assignment_id') != ASSIGNMENT:
        raise ValueError('selected config assignment mismatch')
    packet = args.output_dir / config['reviewed_packet']
    sources = args.output_dir / config['reviewed_source_root']
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    print(json.dumps(run(client, packet, sources, args.output_dir,
                         config['selected_case_id'], carla_module=carla), sort_keys=True))


if __name__ == '__main__':
    main()
