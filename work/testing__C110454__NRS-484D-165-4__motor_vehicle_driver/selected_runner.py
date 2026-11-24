"""Exact source-reviewed Native parked-headlamp capture and publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from camera_recorder import PROFILE_DIMENSIONS, VIEWS
from lamp_probe import CASE_MODES


def check() -> str:
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    plan_source = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(plan_source).hexdigest() != config['plan_sha256']:
        raise ValueError('exact parked-headlamp plan source changed')
    plan = json.loads(plan_source)
    case_id = config['selected_case_id']
    mode = case_id.removeprefix(config['assignment_id'] + '__')
    if (mode not in CASE_MODES or config['requested_headlamp_mode'] != mode or
            not any(item['case_id'] == case_id and item['requested_headlamp_mode'] == mode
                    for item in plan['cases'])):
        raise ValueError('exact parked-headlamp case or mode changed')
    if (config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or
            config['camera_dimensions'] != {view: list(PROFILE_DIMENSIONS[view]) for view in VIEWS}):
        raise ValueError('original parked-headlamp capture profile changed')
    return case_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print('selected parked-headlamp bundle passed: ' + case_id)
        return
    packet_path = os.environ.get('PARKED_HEADLAMP_SITE_PACKET')
    if not packet_path or not args.output_dir:
        raise ValueError('PARKED_HEADLAMP_SITE_PACKET and output directory required')
    packet = json.loads(Path(packet_path).read_text(encoding='utf-8'))
    if (packet.get('format') != 'parked-headlamp-site-v1' or
            packet.get('case_id') != case_id or packet.get('diagnostic_fixture') is not False):
        raise ValueError('reviewed exact Native site packet required')
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture, write_result
    from owned_capture import capture_owned
    from acquisition_finalizer import finalize_acquisition
    from analysis import build
    from native_publication import publish

    def transform(spec):
        return carla.Transform(
            carla.Location(x=spec['x_m'], y=spec['y_m'], z=spec['z_m']),
            carla.Rotation(pitch=spec.get('pitch_deg', 0.0),
                           yaw=spec.get('yaw_deg', 0.0),
                           roll=spec.get('roll_deg', 0.0)))

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    output = Path(args.output_dir)
    capture_owned(client, packet_path, output, case_id=case_id,
                  mode=case_id.rsplit('__', 1)[-1], transform_factory=transform,
                  control_factory=carla.VehicleControl,
                  light_enum=carla.VehicleLightState,
                  pipeline_factory=PipelineCapture)
    finalize_acquisition(output, case_id=case_id)
    report = build(output)
    (output / 'analysis-report.json').write_text(json.dumps(report, indent=2) + '\n',
                                                 encoding='utf-8')
    write_result(output, publish(output, report))
    seal_capture(output, frames=900,
                 restoration={'restored': True, 'settings_readback': 'original map and settings restored'},
                 errors=[], encoder_exit_codes={view: 0 for view in VIEWS},
                 context={'case_id': case_id,
                          'site_sha256': hashlib.sha256((output / 'site-packet.json').read_bytes()).hexdigest()})


if __name__ == '__main__':
    main()
