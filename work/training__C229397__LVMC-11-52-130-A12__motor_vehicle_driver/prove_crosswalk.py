"""CPU proof for source-bound 20-foot crosswalk distance diagnostics."""
import hashlib
import json
from pathlib import Path

from crosswalk_measure import ASSIGNMENT, TWENTY_FEET_M, body_rect_distance, measure


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def sample(x):
    inventory = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
                 'jurisdiction_source_id': 'synthetic-jurisdiction',
                 'marked_crosswalk_source_id': 'synthetic-painted-marking-survey',
                 'crosswalk_extent_source_id': 'synthetic-map-readback',
                 'responsible_person_source_id': 'synthetic-driver-source',
                 'traffic_conflict_review_source_id': 'synthetic-traffic-review',
                 'law_compliance_review_source_id': 'synthetic-law-context-review',
                 'directions_review_source_id': 'synthetic-officer-device-review',
                 'crosswalk_rect_xyxy_m': [0.0, 4.0, -3.5, 0.0]}
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
              'vehicle_id': 'ego', 'frames': [
                  {'video_frame': i, 'native_frame': i+100, 'time_s': i/20,
                   'vehicle_id': 'ego', 'vehicle_xy_m': [x, -1.75], 'yaw_rad': 0.0,
                   'bbox_half_length_m': 2.0, 'bbox_half_width_m': .85,
                   'speed_mps': 0.0 if 200 <= i < 500 else 2.0}
                  for i in range(600)]}
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
    assignment_raw = (source/'assignment.json').read_bytes()
    witness_raw = (source/'witnesses.json').read_bytes()
    if hashlib.sha256(assignment_raw).hexdigest() != '552146163a826b12bc0e6e3cd70fff35168817def6b910b855cae2bb563d03ac':
        raise ValueError('frozen assignment hash changed')
    if hashlib.sha256(witness_raw).hexdigest() != '85a52c58f8d783f39eb018a16ee8dce31b67554f4ead50c7fc16600f2fb0c8c5':
        raise ValueError('frozen witness hash changed')
    law = json.loads(assignment_raw)['law']['text']
    if 'Within twenty feet of any marked crosswalk' not in law or 'except when necessary' not in law:
        raise ValueError('exact law text changed')
    far, inv_far = sample(-14.0)
    near, inv_near = sample(-5.0)
    a, b = measure(encoded(far), encoded(inv_far)), measure(encoded(near), encoded(inv_near))
    if a['halt_body_distance_below_20ft_frames'] or a['halt_center_distance_below_20ft_frames']:
        raise ValueError('far parking entered the 20-foot diagnostic band')
    if b['halt_body_distance_below_20ft_frames'] != list(range(200,500)) or b['halt_center_distance_below_20ft_frames'] != list(range(200,500)):
        raise ValueError('near parking missed the 20-foot diagnostic band')
    if b['halt_proxy_spans'] != [{'first_frame': 200, 'last_frame_inclusive': 499,
                                   'sampled_duration_s': 15.0,
                                   'minimum_body_distance_m': 3.0,
                                   'maximum_body_distance_m': 3.0}]:
        raise ValueError('continuous halt span differs')
    if a['body_to_crosswalk_m_by_frame'][250] != 12 or b['body_to_crosswalk_m_by_frame'][250] != 3:
        raise ValueError('full-body distance differs')
    boundary, inv_boundary = sample(-8.096)
    at = measure(encoded(boundary), encoded(inv_boundary))
    if abs(at['body_to_crosswalk_m_by_frame'][250] - TWENTY_FEET_M) > 1e-9:
        raise ValueError('exact 20-foot body distance differs')
    if body_rect_distance([(-2, -2), (6, -2), (6, 2), (-2, 2)], [0, 4, -1, 1]) != 0:
        raise ValueError('contained crosswalk must overlap vehicle body')
    if body_rect_distance([(-5, -1), (-3, -1), (-3, 1), (-5, 1)], [0, 4, -1, 1]) != 3:
        raise ValueError('separated body gap differs')
    if a['legal_result'] is not None or b['legal_result'] is not None:
        raise ValueError('legal conclusion asserted')
    packet, inv = sample(-5)
    inv['marked_crosswalk_source_id'] = None
    reject(packet, inv, 'marked_crosswalk_source_id missing')
    packet, inv = sample(-5)
    inv['directions_review_source_id'] = None
    reject(packet, inv, 'directions_review_source_id missing')
    packet, inv = sample(-5)
    packet['frames'][250]['vehicle_id'] = 'other'
    reject(packet, inv, 'subject identity changed')
    packet, inv = sample(-5)
    packet['frames'].pop(250)
    reject(packet, inv, '600 original frames required')
    print(json.dumps({'passed': True, 'law_sha256': hashlib.sha256(law.encode()).hexdigest(),
                      'assignment_sha256': hashlib.sha256(assignment_raw).hexdigest(),
                      'witness_sha256': hashlib.sha256(witness_raw).hexdigest(),
                      'far_packet_sha256': a['packet_sha256'], 'near_packet_sha256': b['packet_sha256'],
                      'far_body_gap_m': 12, 'near_body_gap_m': 3,
                      'boundary_body_gap_m': at['body_to_crosswalk_m_by_frame'][250],
                      'twenty_feet_m': TWENTY_FEET_M,
                      'checks': ['600-frame 20Hz', 'continuous sampled halt span',
                                 'full-body/center/longitudinal distances',
                                 'exact boundary and polygon containment',
                                 'marked-crosswalk-source rejection', 'exception-source rejection',
                                 'identity rejection', 'missing-frame rejection']}, sort_keys=True))


if __name__ == '__main__':
    main()
