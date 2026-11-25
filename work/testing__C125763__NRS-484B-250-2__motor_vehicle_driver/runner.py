"""Exact C125763 bundle preflight and source-gated Native entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_construction import reviewed_scene
from native_run import CASES, PRODUCTION_DIMENSIONS, run


def check_bundle(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    prefix = 'testing__C125763__NRS-484B-250-2__motor_vehicle_driver__'
    if (config.get('law_id') != 'NRS-484B-250-2' or
            config.get('cell_id') != 'C125763' or
            config.get('actor') != 'motor_vehicle_driver' or
            case_id not in {prefix + case for case in CASES}):
        raise ValueError('exact C125763 bundle identity differs')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('original capture clock differs')
    cameras = config.get('cameras', [])
    if {camera.get('name'): [camera.get('width'), camera.get('height')]
            for camera in cameras} != PRODUCTION_DIMENSIONS or len(cameras) != 4:
        raise ValueError('original four-camera profile differs')
    site = json.loads((root / 'site.json').read_text(encoding='utf-8'))
    if site.get('review_status') != 'diagnostic_fixture':
        raise ValueError('offline bundle must be explicitly diagnostic')
    map_text = site.get('diagnostic_map_text')
    if not isinstance(map_text, str) or hashlib.sha256(map_text.encode()).hexdigest() != site.get('map_sha256'):
        raise ValueError('diagnostic map source differs')

    class Map:
        def to_opendrive(self):
            return map_text

    class World:
        def get_map(self):
            return Map()

    reviewed_scene(root / 'site.json', World())
    if site.get('camera_dimensions') != PRODUCTION_DIMENSIONS or (
            set(site.get('release_s', {})) != set(CASES)):
        raise ValueError('diagnostic site capture profile or schedules differ')
    return {'case_id': case_id, 'diagnostic_fixture': True,
            'source_packet_sha256': hashlib.sha256((root / 'site.json').read_bytes()).hexdigest(),
            'original_capture_started': False, 'physical_acceptance': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    checked = check_bundle(root)
    if args.check:
        if args.output_dir:
            parser.error('--check and --output-dir are exclusive')
        print(json.dumps(checked, sort_keys=True))
        return
    if not args.output_dir or not args.packet:
        parser.error('original capture needs --output-dir and --packet')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    case = checked['case_id'].rsplit('__', 1)[1]
    print(json.dumps(run(client.get_world(), carla, args.packet, args.output_dir,
                         case), sort_keys=True))


if __name__ == '__main__':
    main()
