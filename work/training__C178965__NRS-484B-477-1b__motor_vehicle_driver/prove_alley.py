"""CPU proof of source-bound 30-second width computation and rejection."""
import hashlib
import json
import math
from pathlib import Path

from alley_measure import ASSIGNMENT, measure, TEN_FEET_M


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def sample(width):
    inventory = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
                 'public_highway_source_id': 'synthetic-public-highway',
                 'city_block_source_id': 'synthetic-block-survey',
                 'rear_access_source_id': 'synthetic-rear-access-survey',
                 'abutting_property_source_id': 'synthetic-abutting-parcels',
                 'non_culdesac_source_id': 'synthetic-open-ends',
                 'local_jurisdiction_source_id': 'synthetic-jurisdiction',
                 'local_ordinance_review_source_id': 'synthetic-ordinance-review',
                 'other_alley_scope_review_source_id': 'synthetic-antecedent-review',
                 'halt_purpose_review_source_id': 'synthetic-purpose-review',
                 'occupant_activity_review_source_id': 'synthetic-occupant-review',
                 'traffic_conflict_review_source_id': 'synthetic-conflict-review',
                 'official_direction_review_source_id': 'synthetic-direction-review',
                 'boundary_measurement_source_id': 'synthetic-map-width-survey',
                 'alley_lateral_edges_m': [-width, 0.0]}
    rows = []
    for i in range(600):
        rows.append({'video_frame': i, 'native_frame': i + 100, 'time_s': i / 20,
                     'subject': {'vehicle_id': 'subject', 'xy_m': [0, -width + 1],
                                 'yaw_rad': 0.0, 'half_length_m': 2.0,
                                 'half_width_m': .8, 'speed_mps': 0.0 if 200 <= i < 500 else 2.0},
                     'other': {'vehicle_id': 'other', 'xy_m': [0, -1],
                               'yaw_rad': 0.0, 'half_length_m': 2.0,
                               'half_width_m': .8}})
    return {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
            'subject_id': 'subject', 'other_id': 'other', 'frames': rows}, inventory


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
    if hashlib.sha256(assignment_raw).hexdigest() != '6df1a6c4e7679bb171ec6ed0dd1eebbf0a01864976ecf80452dad3313de1eff5':
        raise ValueError('frozen assignment hash changed')
    if hashlib.sha256(witness_raw).hexdigest() != 'bff80e2a64411879a480996bce7de1382155f49a5f14baeedcba2e985081efac':
        raise ValueError('frozen witness hash changed')
    law = json.loads(assignment_raw)['law']['text']
    if 'less than 10 feet' not in law or 'Unless otherwise provided by ordinance' not in law:
        raise ValueError('source law changed')
    wide, inv_wide = sample(7.5)
    at, inv_at = sample(6.648)
    narrow, inv_narrow = sample(6.0)
    a = measure(encoded(wide), encoded(inv_wide))
    midpoint = measure(encoded(at), encoded(inv_at))
    b = measure(encoded(narrow), encoded(inv_narrow))
    if not math.isclose(midpoint['minimum_measured_halt_free_width_m'], TEN_FEET_M,
                        rel_tol=0, abs_tol=1e-9):
        raise ValueError('exact ten-foot sample differs')
    if midpoint['measured_halt_frames_below_10_feet']:
        raise ValueError('exact ten-foot sample was incorrectly classified below')
    if not a['minimum_measured_halt_free_width_m'] > TEN_FEET_M:
        raise ValueError('wide alley sample did not leave 10 feet')
    if not b['minimum_measured_halt_free_width_m'] < TEN_FEET_M:
        raise ValueError('narrow alley sample did not leave under 10 feet')
    if a['subject_halt_proxy_frames'] != list(range(200, 500)) or b['subject_halt_proxy_frames'] != list(range(200, 500)):
        raise ValueError('halt interval changed')
    if a['measured_halt_frames_below_10_feet'] or b['measured_halt_frames_below_10_feet'] != list(range(200, 500)):
        raise ValueError('threshold interval changed')
    packet, inventory = sample(6)
    inventory['local_ordinance_review_source_id'] = ''
    reject(packet, inventory, 'local_ordinance_review_source_id missing')
    packet, inventory = sample(6)
    inventory['rear_access_source_id'] = ''
    reject(packet, inventory, 'rear_access_source_id missing')
    packet, inventory = sample(6)
    inventory['halt_purpose_review_source_id'] = ''
    reject(packet, inventory, 'halt_purpose_review_source_id missing')
    packet, inventory = sample(6)
    packet['frames'][200]['other']['vehicle_id'] = 'other2'
    reject(packet, inventory, 'vehicle identity changed')
    packet, inventory = sample(6)
    packet['frames'].pop(200)
    reject(packet, inventory, '600 original frames required')
    print(json.dumps({'passed': True, 'law_sha256': hashlib.sha256(law.encode()).hexdigest(),
                      'assignment_sha256': hashlib.sha256(assignment_raw).hexdigest(),
                      'witness_sha256': hashlib.sha256(witness_raw).hexdigest(),
                      'wide_packet_sha256': a['packet_sha256'],
                      'narrow_packet_sha256': b['packet_sha256'],
                      'wide_free_width_m': a['minimum_measured_halt_free_width_m'],
                      'at_free_width_m': midpoint['minimum_measured_halt_free_width_m'],
                      'narrow_free_width_m': b['minimum_measured_halt_free_width_m'],
                      'checks': ['600 original 20-Hz frames', 'both vehicle footprints',
                                 '10-foot statutory comparison without legal verdict',
                                 'local ordinance source rejection', 'alley definition source rejection',
                                 'parking-purpose source rejection',
                                 'identity rejection', 'missing frame rejection']}, sort_keys=True))


if __name__ == '__main__':
    main()
