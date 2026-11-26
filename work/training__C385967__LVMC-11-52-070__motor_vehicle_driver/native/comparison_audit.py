"""Independent source-hash comparison of the paired angle-park orientations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_measure import NAMES, process, sha

PREFIX = 'training__C385967__LVMC-11-52-070__motor_vehicle_driver__probe_'


def audit(left, right, *, allow_fixture=False):
    attempts = [Path(left), Path(right)]
    fixed = []
    measured = []
    hashes = []
    for suffix, yaw, attempt in zip(('a','b'), (45,225), attempts):
        config_path = attempt/'config.json'
        if not config_path.is_file():
            raise ValueError('Missing exact comparison config')
        config = json.loads(config_path.read_text())
        case = PREFIX+suffix
        if config.get('case_id') != case or config.get('requested_front_yaw_deg') != yaw:
            raise ValueError('Comparison case or orientation request differs')
        shape = (config.get('law_id'), config.get('cell_id'), config.get('actor'),
            config.get('layout'), config.get('maneuver'), config.get('control'),
            config.get('rate_hz'), config.get('duration_s'),
            tuple((c.get('name'), c.get('fps'), c.get('width'), c.get('height'))
                  for c in config.get('cameras', [])))
        if shape[:8] != ('LVMC-11-52-070','C385967','motor_vehicle_driver',
                         'one_way_road','angle_park','angle_parking_designation',20,30):
            raise ValueError('Comparison fixed scene changed')
        if shape[8] != (('overview',20,1920,1080),('approach',20,1280,720),
                        ('reference_corner',20,1280,720),('driver_reference',20,1280,720)):
            raise ValueError('Comparison fixed camera plan changed')
        result = process(attempt, config, allow_fixture=allow_fixture)
        if not allow_fixture and result['source_kind'] != 'original_native_capture':
            raise ValueError('Original Native comparison source required')
        fixed.append(shape)
        measured.append(result['measurement']['direction'])
        hashes.append({name:sha(attempt/name) for name in NAMES})
    if fixed[0] != fixed[1] or measured != [
            'front_with_lawful_flow','front_against_lawful_flow']:
        raise ValueError('Only planned orientation contrast was not observed')
    return {'format':'c385967-independent-comparison-v1',
        'case_ids':[PREFIX+'a',PREFIX+'b'],
        'deliberate_difference':'requested_front_yaw_deg',
        'measured_directions':measured,'source_hashes':hashes,
        'diagnostic_fixture':allow_fixture,
        'city_permission_verified':False,'legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--left-attempt',type=Path,required=True)
    p.add_argument('--right-attempt',type=Path,required=True)
    p.add_argument('--allow-fixture',action='store_true')
    a=p.parse_args()
    print(json.dumps(audit(a.left_attempt,a.right_attempt,allow_fixture=a.allow_fixture),indent=2))
