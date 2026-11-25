"""Exact reviewed-source Native capture entrypoint for C104084.

Run only after a reviewer supplies original source documents, a matching live
OpenDRIVE map and reviewed Native actor/camera setup. No fixture is accepted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from carla_delegate import CarlaDelegate
from native_capture import capture
from native_source_adapter import ReviewedAdapter

ASSIGNMENT = 'testing__C104084__NRS-484B-213-2a__motor_vehicle_driver'


def run(client, packet_path, source_root, output, case_id, *, carla_module=None):
    output = Path(output)
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError('fresh empty original attempt directory required')
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if case_id != packet.get('case_id') or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('reviewed Native packet and exact case differ')
    delegate = CarlaDelegate(client, packet, case_id, output, carla_module=carla_module)
    adapter = ReviewedAdapter(delegate, packet_path=packet_path,
                              source_root=Path(source_root), output=output,
                              world=client.get_world())
    result = capture(adapter, output, assignment_id=ASSIGNMENT, case_id=case_id)
    release = delegate.release_receipt()
    if not release['world_restored'] or not release['actors_released'] or not release['sensors_released']:
        raise ValueError('Native owner release readback failed')
    (output / 'owner-release.json').write_text(json.dumps(release, indent=2,
                                                        sort_keys=True) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    result = run(client, args.packet, args.source_root, args.output_dir,
                 args.case, carla_module=carla)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
