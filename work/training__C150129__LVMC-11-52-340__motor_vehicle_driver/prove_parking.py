"""CPU source-shape and rejection proof for the 30-second parking diagnostic."""
import hashlib
import json
from pathlib import Path

from parking_measure import ASSIGNMENT, measure


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def sample(x=0.0):
    inventory = {
        'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
        'city_street_source_id': 'synthetic-jurisdiction-document',
        'council_designation_source_id': 'synthetic-council-record',
        'space_id': 'city-space-01', 'posting_space_id': 'city-space-01',
        'posting_or_marking_source_id': 'synthetic-sign-survey',
        'subject_status_source_id': 'synthetic-registration-record',
        'subject_city_vehicle': False,
        'space_polygon_xy_m': [[-6.0, -7.0], [6.0, -7.0], [6.0, -3.5], [-6.0, -3.5]],
    }
    packet = {
        'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
        'vehicle_id': 'ego',
        'frames': [{'video_frame': i, 'native_frame': i + 100, 'time_s': i / 20,
                    'vehicle_id': 'ego', 'vehicle_xy_m': [x, -5.2], 'yaw_rad': 0.0,
                    'bbox_half_length_m': 2.0, 'bbox_half_width_m': .8,
                    'speed_mps': 0.0 if 200 <= i < 500 else 2.0}
                   for i in range(600)],
    }
    return packet, inventory


def reject(packet, inventory, expected):
    try:
        measure(encoded(packet), encoded(inventory))
    except ValueError as exc:
        if str(exc) == expected:
            return
        raise
    raise RuntimeError('invalid source accepted: ' + expected)


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / 'inputs' / ASSIGNMENT
    assignment_raw = (source / 'assignment.json').read_bytes()
    witness_raw = (source / 'witnesses.json').read_bytes()
    if hashlib.sha256(assignment_raw).hexdigest() != '4aef87cdf566fe21ca02d41e2d85cd4dacf20dd3a3216ef8460b3271367315e7':
        raise ValueError('frozen assignment hash changed')
    if hashlib.sha256(witness_raw).hexdigest() != '6a7e4d7bdea540d8fee52f670a622ed67986dd9dafe47c88793f462d1ac532d3':
        raise ValueError('frozen witness hash changed')
    law = json.loads(assignment_raw)['law']['text']
    if 'City Council may designate' not in law or 'duly posted or marked' not in law:
        raise ValueError('source law changed')
    inside, inventory = sample()
    positive = measure(encoded(inside), encoded(inventory))
    if positive['occupied_frames'] != list(range(600)) or positive['occupied_and_stationary_proxy_frames'] != list(range(200, 500)):
        raise ValueError('inside measured interval differs')
    outside, inventory = sample(x=20)
    negative_geometry = measure(encoded(outside), encoded(inventory))
    if negative_geometry['occupied_frames']:
        raise ValueError('outside footprint counted as occupied')
    packet, inventory = sample()
    inventory['council_designation_source_id'] = ''
    reject(packet, inventory, 'City Council designation source missing')
    packet, inventory = sample()
    inventory['posting_space_id'] = 'other'
    reject(packet, inventory, 'posting-space association missing')
    packet, inventory = sample()
    inventory['subject_city_vehicle'] = None
    reject(packet, inventory, 'non-City vehicle source missing')
    packet, inventory = sample()
    packet['frames'][250]['vehicle_id'] = 'other'
    reject(packet, inventory, 'subject vehicle identity changed')
    packet, inventory = sample()
    packet['frames'].pop(250)
    reject(packet, inventory, '600 original frames required')
    print(json.dumps({'passed': True, 'law_sha256': hashlib.sha256(law.encode()).hexdigest(),
                      'assignment_sha256': hashlib.sha256(assignment_raw).hexdigest(),
                      'witness_sha256': hashlib.sha256(witness_raw).hexdigest(),
                      'inside_packet_sha256': positive['packet_sha256'],
                      'outside_packet_sha256': negative_geometry['packet_sha256'],
                      'inventory_sha256': positive['inventory_sha256'],
                      'checks': ['600-frame 20-Hz timing', 'rotated footprint occupancy',
                                 'stationary proxy separate from legal parking',
                                 'designation source rejection', 'posted-space join rejection',
                                 'subject status rejection', 'identity rejection', 'frame rejection']}, sort_keys=True))


if __name__ == '__main__':
    main()
