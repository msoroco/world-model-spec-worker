"""Exact selected angle-parking case runner."""
import argparse
import json
from pathlib import Path

from capture import check as capture_check, capture


def check(config):
    base = 'training__C385967__LVMC-11-52-070__motor_vehicle_driver__probe_'
    expected = {base+'a': 45, base+'b': 225}
    case = config.get('case_id')
    if case not in expected or config.get('selected_case_id') != case:
        raise ValueError('Exact selected case differs')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != \
            ('LVMC-11-52-070', 'C385967', 'motor_vehicle_driver'):
        raise ValueError('Frozen assignment identity differs')
    if config.get('requested_front_yaw_deg') != expected[case] or \
            (config.get('rate_hz'), config.get('duration_s'),
             config.get('duration_frames')) != (20, 30, 600):
        raise ValueError('Angle branch or full window differs')
    if config.get('layout') != 'one_way_road' or \
            config.get('maneuver') != 'angle_park' or \
            config.get('control') != 'angle_parking_designation':
        raise ValueError('Frozen scene differs')
    if config.get('required_atoms') != ['kin.heading', 'kin.speed']:
        raise ValueError('Supported native telemetry differs')
    return capture_check(config)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--host')
    p.add_argument('--port', type=int)
    a = p.parse_args()
    cfg = json.loads(Path('config.json').read_text())
    if a.check:
        print(json.dumps(check(cfg), sort_keys=True))
    else:
        if not (a.output_dir and a.host and a.port):
            p.error('Original capture needs --output-dir, --host and --port')
        print(json.dumps(capture(cfg, Path(a.output_dir), a.host, a.port), sort_keys=True))
