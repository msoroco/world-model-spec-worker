"""Source-gated exact one-way Native entrypoint."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from one_way_direction import CASES
from reviewed_source import verify

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config: dict) -> bool:
    expected = {ASSIGNMENT + '__' + case.name for case in CASES}
    if (config.get('selected_case_id') not in expected or
            set(config.get('supported_case_ids', [])) != expected or
            config.get('law_id') != 'NRS-484B-220-1' or
            config.get('cell_id') != 'C147311' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('exact one-way assignment/case mismatch')
    cameras = config.get('cameras', [])
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            [(c.get('name'), c.get('width'), c.get('height')) for c in cameras]
            != [('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)] or
            not all(c.get('pose_strategy') and c.get('fov_deg') for c in cameras) or
            config.get('diagnostic_only') is not False):
        raise ValueError('one-way capture contract mismatch')
    case = next(c for c in CASES if config['selected_case_id'].endswith('__' + c.name))
    if config.get('case', {}).get('variant') != case.name or config['case'].get('lane') != case.lane or config['case'].get('direction') != case.direction:
        raise ValueError('one-way selected variant mismatch')
    if config.get('reverse_motion') is not (case.direction == 'opposed') or config.get('requested_speed_mps') != 5.0:
        raise ValueError('physical motion direction differs from exact selected route')
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text(encoding='utf-8'))
    check_config(config)
    if args.check:
        print('four-case source-gated one-way construction passed')
        return
    if args.output_dir is None:
        raise ValueError('Native output directory required')
    source = os.environ.get('C147311_REVIEWED_SITE_PACKET')
    adapter = None
    try:
        if not source:
            raise ValueError('original reviewed site packet path required')
        reviewed = verify(Path(source), config['case']['variant'])
        from native_adapter import NativeAdapter
        adapter = NativeAdapter(args.host, args.port, args.output_dir, Path(source))
        adapter.execute(reviewed, config)
        adapter.close()
        if not adapter.restoration_verified:
            raise ValueError('original Native restoration unverified')
        output = args.output_dir
        packet = json.loads(Path(source).read_text(encoding='utf-8'))
        shutil.copy2(source, output / 'site-source.json')
        for binding in packet['source_bindings'].values():
            destination = output / binding['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source).parent / binding['path'], destination)
        for camera in CAMERAS:
            frames = output / 'capture' / camera
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error',
                            '-nostdin', '-framerate', '20', '-start_number', '0',
                            '-i', str(frames / '%06d.png'), '-frames:v', '900',
                            '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                            str(output / (camera + '.mkv'))],
                           check=True, timeout=600)
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}) + '\n', encoding='utf-8')
        from analysis import analyze, saved_result
        from worker_exchange.native_output import seal_capture, write_result
        report = analyze(output, config['selected_case_id'])
        result = saved_result(output, report)
        write_result(output, result)
        seal_capture(output, frames=900,
                     restoration={'restored': True,
                                  'settings_readback': 'synchronous mode and delta verified'},
                     errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                     context={'site_sha256': reviewed['site_sha256'],
                              'source_hashes': reviewed['source_hashes']})
    except BaseException as error:
        if args.output_dir.is_dir():
            (args.output_dir / 'native-run-status.json').write_text(json.dumps({
                'errors': [repr(error)], 'physical_acceptance_claimed': False}) + '\n',
                encoding='utf-8')
        raise
    finally:
        if adapter is not None and not getattr(adapter, 'restoration_verified', False):
            adapter.close()


if __name__ == '__main__':
    main()
