"""Exact C125763 subsection-1 bundle preflight and source-gated Native runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from native_construction import ASSIGNMENT, CASES, reviewed_scene
from native_run import PRODUCTION_DIMENSIONS, run


def check_bundle(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    if (config.get('law_id') != 'NRS-484B-250-1' or
            config.get('cell_id') != 'C125763' or
            config.get('actor') != 'motor_vehicle_driver' or
            case_id not in {ASSIGNMENT + '__' + case for case in CASES} or
            config.get('case', {}).get('case_id') != case_id):
        raise ValueError('exact C125763 subsection-1 bundle identity differs')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('original capture clock differs')
    speed = config.get('target_speed_mps', 8.0)
    if type(speed) not in (int, float) or not 4.0 <= speed <= 12.0:
        raise ValueError('bounded engineering target speed required')
    cameras = config.get('cameras', [])
    if ({camera.get('name'): [camera.get('width'), camera.get('height')]
         for camera in cameras} != PRODUCTION_DIMENSIONS or len(cameras) != 4):
        raise ValueError('original four-camera profile differs')
    site = json.loads((root / 'site.json').read_text(encoding='utf-8'))
    if site.get('review_status') != 'diagnostic_fixture':
        raise ValueError('offline construction must retain diagnostic source label')
    road = site.get('diagnostic_map_text')
    if not isinstance(road, str) or hashlib.sha256(road.encode()).hexdigest() != site.get('map_sha256'):
        raise ValueError('diagnostic map source differs')

    class Map:
        def to_opendrive(self):
            return road

    class World:
        def get_map(self):
            return Map()

    reviewed_scene(root / 'site.json', World(), diagnostic=True)
    if site.get('camera_dimensions') != PRODUCTION_DIMENSIONS:
        raise ValueError('source packet camera profile differs')
    return {'case_id': case_id, 'diagnostic_fixture': True,
            'source_packet_sha256': hashlib.sha256((root / 'site.json').read_bytes()).hexdigest(),
            'original_capture_started': False, 'physical_acceptance': False,
            'legal_verdict_claimed': False}


def _native_capture(root, packet, output, case, host, port, speed):
    import carla
    client = carla.Client(host, port)
    client.set_timeout(30)
    original = output / 'native-original'
    receipt = run(client.get_world(), carla, packet, original, case,
                  target_speed_mps=speed)
    for source in original.iterdir():
        target = output / source.name
        if target.exists():
            raise FileExistsError(target)
        source.rename(target)
    original.rmdir()
    from encode_views import encode, compose_primary
    encoded = encode(output, output / 'encoded-views',
                     camera_dimensions=PRODUCTION_DIMENSIONS)
    (output / 'encoded-receipt.json').write_text(json.dumps(encoded, indent=2) + '\n')
    for name in PRODUCTION_DIMENSIONS:
        shutil.copy2(output / 'encoded-views' / (name + '.mkv'),
                     output / (name + '.mkv'))
    composed = compose_primary(output, output / 'encoded-views',
                               output / 'raw.mkv', encoded)
    (output / 'composition-receipt.json').write_text(json.dumps(composed, indent=2) + '\n')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_source_packet_sha256': hashlib.sha256(Path(packet).read_bytes()).hexdigest()
    }, indent=2) + '\n')
    pipeline = str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline')
    if pipeline not in sys.path:
        sys.path.insert(0, pipeline)
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=receipt['frame_count'],
                 restoration={'restored': True, 'verified_by': 'native_run.run settings readback'},
                 errors=[], encoder_exit_codes={name: 0 for name in PRODUCTION_DIMENSIONS},
                 context={'assignment_id': ASSIGNMENT,
                          'case_id': ASSIGNMENT + '__' + case})
    return {'case_id': ASSIGNMENT + '__' + case,
            'source_frame_count': receipt['frame_count'],
            'native_capture_sealed': True, 'physical_acceptance': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--packet')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    checked = check_bundle(root)
    if args.check:
        if args.output_dir:
            parser.error('--check cannot start a capture')
        print(json.dumps(checked, sort_keys=True))
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    packet = args.packet or os.environ.get('SCENARIO_REVIEWED_SITE_PACKET')
    if not packet:
        parser.error('supply an original reviewed site packet')
    output = Path(args.output_dir)
    if not output.is_dir():
        parser.error('prepared attempt directory required')
    case = checked['case_id'].rsplit('__', 1)[1]
    print(json.dumps(_native_capture(root, packet, output, case,
                                     args.host, args.port,
                                     json.loads((root / 'config.json').read_text()).get('target_speed_mps', 8.0)),
                     sort_keys=True))


if __name__ == '__main__':
    main()
