"""Source-bound light-express freight variants for the yellow-curb taxi cell.

The fixture and request checks here establish software behavior only. They do
not decide whether a particular taxicab qualifies under LVMC 11.52.030(B)(1).
"""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

PREFIX = 'training__C150173__LVMC-11-52-030-B__taxi_driver__'
PURPOSES = {
    'freight_load': 'loading_light_express',
    'freight_unload': 'unloading_light_express',
    'freight_wait': 'waiting_without_transfer',
}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_request(config, road_text):
    case = config.get('case_id', '')
    suffix = case[len(PREFIX):] if case.startswith(PREFIX) else None
    if (suffix not in PURPOSES or config.get('selected_case_id') != case or
            config.get('assignment_id') != PREFIX[:-2] or
            config.get('law_id') != 'LVMC-11-52-030-B' or
            config.get('cell_id') != 'C150173' or
            config.get('actor') != 'taxi_driver' or
            config.get('requested_purpose') != PURPOSES.get(suffix) or
            config.get('duration_s') != 30 or config.get('rate_hz') != 20 or
            config.get('frames') != 600 or config.get('legal_verdict') is not None):
        raise ValueError('Exact light-express taxi request differs')
    if config.get('commercial_classification') != 'pending_original_review':
        raise ValueError('Commercial status must await original review')
    if config.get('sign_source_status') != 'authored_proposal_unverified':
        raise ValueError('Freight sign authority must await original review')
    if tuple(c.get('name') for c in config.get('cameras', [])) != VIEWS:
        raise ValueError('Four original cameras required')
    if any(c.get('fps') != 20 or not all(c.get(k) for k in
           ('width', 'height', 'fov_deg', 'pose_strategy'))
           for c in config['cameras']):
        raise ValueError('Camera source plan incomplete')
    start = datetime.fromisoformat(config['civil_start_local'])
    if start.tzinfo is not None or (start.hour, start.minute, start.second) != (10, 0, 0):
        raise ValueError('Controlled posted-hour civil time differs')
    road = ET.fromstring(road_text).find('road')
    if road is None or road.find('./planView/geometry/line') is None:
        raise ValueError('One-way freight road missing')
    lanes = {(n.get('id'), n.get('type')) for n in road.findall('./lanes/laneSection/right/lane')}
    if not {('-1', 'driving'), ('-2', 'parking'), ('-3', 'sidewalk')} <= lanes:
        raise ValueError('Driving, parking or sidewalk lane missing')
    if not any(n.get('color') == 'yellow' for n in
               road.findall('./lanes/laneSection/right/lane[@id="-2"]/roadMark')):
        raise ValueError('Yellow freight curb missing')
    if not any(n.get('name') == 'COMMERCIAL FREIGHT 09:00-17:00 PROPOSAL'
               for n in road.findall('./signals/signal')):
        raise ValueError('Freight-specific posted sign proposal missing')
    if not any(n.get('id') == '701' for n in road.findall('./objects/object')):
        raise ValueError('Yellow curb zone geometry missing')
    return {'case_id': case, 'requested_purpose': PURPOSES[suffix],
            'frames': 600, 'rate_hz': 20, 'commercial_status_verified': False,
            'sign_authority_verified': False, 'freight_transfer_verified': False,
            'legal_verdict': None}


def measure_saved(rows, config):
    if len(rows) != 600:
        raise ValueError('Full freight source interval required')
    purpose = config['requested_purpose']
    start = datetime.fromisoformat(config['civil_start_local'])
    first = last = None
    transfer_frames = 0
    for i, row in enumerate(rows):
        if (row.get('video_frame') != i or
                not math.isclose(row.get('time_s', -1), (i + 1) / 20, abs_tol=1e-4) or
                row.get('source_kind') not in ('original_native', 'synthetic_cpu_fixture') or
                row.get('observed_purpose') != purpose or
                row.get('taxi_actor_id') is None or row.get('cargo_actor_id') is None):
            raise ValueError('Freight source identity/frame join differs')
        if datetime.fromisoformat(row['civil_time_local']) != start + timedelta(seconds=(i + 1) / 20):
            raise ValueError('Freight civil time join differs')
        taxi = row.get('taxi_body_vertices_xyz_m')
        cargo = row.get('cargo_body_vertices_xyz_m')
        if (not isinstance(taxi, list) or len(taxi) != 8 or
                not isinstance(cargo, list) or len(cargo) != 8 or
                any(not isinstance(v, list) or len(v) != 3 or
                    any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
                    for v in taxi + cargo)):
            raise ValueError('Original taxi/cargo body geometry missing')
        centre = [sum(v[j] for v in cargo) / 8 for j in range(3)]
        if first is None:
            first = centre
        last = centre
        transfer_frames += bool(row.get('cargo_transfer_motion_observed'))
    displacement = math.dist(first, last)
    return {'case_id': config['case_id'], 'observed_purpose': purpose,
            'frames': 600, 'cargo_displacement_m': displacement,
            'cargo_transfer_motion_frames': transfer_frames,
            'source_kind': rows[0]['source_kind'],
            'commercial_status_review_required': True,
            'posted_sign_review_required': True,
            'actual_freight_purpose_review_required': True,
            'legal_verdict': None}


def read_saved(path, config):
    return measure_saved([json.loads(line) for line in Path(path).read_text().splitlines()], config)
