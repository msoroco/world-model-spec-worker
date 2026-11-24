"""Source-bound 30-second flashing-yellow-arrow turn requests, not Native evidence."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ASSIGNMENT = Path(__file__).with_name('assignment-source.json')
TEMPLATE = Path(__file__).with_name('road-template.xodr')
CASES = {'yield_then_turn': 320, 'turn_during_other_passage': 200}
RATE_HZ = 20
FRAMES = 600
INTERSECTION = (-4.0, 4.0, -4.0, 4.0)


def law():
    if hashlib.sha256(ASSIGNMENT.read_bytes()).hexdigest() != '78c678eebf680dfab96a595bbbe68117badf262a400e4ab6142fb303b831d1fd':
        raise ValueError('Frozen assignment source packet changed')
    source = json.loads(ASSIGNMENT.read_text())
    text = source['law']['text']
    required = ('flashing yellow turn arrow', 'cautiously enter the intersection',
                'pedestrians lawfully within', 'other traffic lawfully within')
    if source['law']['id'] != 'NRS-484B-307-7a' or any(clause not in text for clause in required):
        raise ValueError('Frozen flashing-arrow source clauses differ')
    return {'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}


def road():
    root = ET.fromstring(TEMPLATE.read_text())
    root.find('header').set('name', 'C111603-flashing-yellow-right-arrow-request')
    signal = root.find("./road[@id='1']/signals/signal")
    if signal is None or signal.attrib['id'] != '601':
        raise ValueError('Frozen other-vehicle intersection approach signal differs')
    signal.set('name', 'south-approach-flashing-yellow-right-arrow-request')
    signal.set('subtype', '1')
    signal.set('dynamic', 'yes')
    return ET.tostring(root, encoding='unicode') + '\n'


def inside(point):
    return INTERSECTION[0] <= point[0] <= INTERSECTION[1] and INTERSECTION[2] <= point[1] <= INTERSECTION[3]


def rows(case):
    if case not in CASES:
        raise ValueError('Unknown exact other-traffic yield case')
    release = CASES[case]
    result = []
    for frame in range(FRAMES):
        time_s = frame / RATE_HZ
        approach_y = min(-5.0, -50.0 + 5 * time_s)
        if frame < release:
            ego_x, ego_y, heading, phase = -1.75, approach_y, math.pi/2, 'approach_or_hold'
        else:
            distance = 5 * (frame-release) / RATE_HZ
            angle = min(math.pi/2, distance/7)
            ego_x = 5.25 - 7*math.cos(angle) + max(0.0, distance - 7*math.pi/2)
            ego_y = -5 + 7*math.sin(angle)
            heading, phase = math.pi/2-angle, 'requested_right_turn'
        other_x = min(35.0, -30.0 + 3*time_s)
        lit = frame % 20 < 10
        result.append({'frame': frame, 'time_s': time_s,
            'requested_ego_xy_m': [round(ego_x, 6), round(ego_y, 6)],
            'requested_ego_heading_rad': round(heading, 8),
            'requested_other_xy_m': [round(other_x, 6), 1.75],
            'requested_other_inside_intersection': inside((other_x, 1.75)),
            'requested_ego_inside_intersection': inside((ego_x, ego_y)),
            'requested_arrow': {'direction': 'right', 'flashing_yellow_lit': lit,
                                'governs_ego': 'requested_unverified', 'other_indications': []},
            'requested_phase': phase, 'requested_release_frame': release,
            'other_traffic_lawful_status': 'external_review_pending',
            'pedestrian_presence_status': 'external_review_pending',
            'cautiousness_legal_judgment': None, 'original_native_observed': False})
    return result


def validate_request(data, case):
    """Reject drift in an authored request; never validate original Native motion."""
    expected = rows(case)
    if len(data) != FRAMES or [r.get('frame') for r in data] != list(range(FRAMES)):
        raise ValueError('Requested frame inventory differs')
    for index, (actual, planned) in enumerate(zip(data, expected)):
        for name in ('time_s', 'requested_ego_xy_m', 'requested_ego_heading_rad',
                     'requested_other_xy_m', 'requested_arrow', 'requested_phase',
                     'requested_release_frame'):
            if actual.get(name) != planned[name]:
                raise ValueError('Requested ' + name + ' changed at frame ' + str(index))
        if actual.get('other_traffic_lawful_status') != 'external_review_pending' or \
                actual.get('cautiousness_legal_judgment') is not None or \
                actual.get('original_native_observed') is not False:
            raise ValueError('Requested source asserts unreviewed physical or legal fact')
    return {'frames': FRAMES, 'case': case, 'requested_track_valid': True,
            'original_native_observed': False}


def check(case):
    source = law()
    xml = ET.fromstring(road())
    signals = xml.findall("./road[@id='1']/signals/signal")
    if len(signals) != 1 or 'flashing-yellow-right-arrow' not in signals[0].attrib['name']:
        raise ValueError('Arrow request source differs')
    data = rows(case)
    validate_request(data, case)
    entering = [r for r in data if r['requested_ego_inside_intersection'] and r['requested_phase']=='requested_right_turn']
    if not entering or not entering[0]['requested_arrow']['flashing_yellow_lit']:
        raise ValueError('Requested entry does not align with lit arrow')
    other_at_entry = entering[0]['requested_other_inside_intersection']
    if other_at_entry != (case == 'turn_during_other_passage'):
        raise ValueError('Controlled other-traffic timing differs')
    if any(r['other_traffic_lawful_status'] != 'external_review_pending' or
           r['cautiousness_legal_judgment'] is not None or r['original_native_observed']
           for r in data):
        raise ValueError('Requested trace claims physical or legal result')
    return {'passed': True, 'case': case, 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'first_requested_entry_frame': entering[0]['frame'],
            'other_requested_inside_at_entry': other_at_entry,
            'law_text_sha256': source['sha256'], 'native_executed': False,
            'official_arrow_status': 'unverified', 'other_traffic_lawful_status': 'unverified',
            'legal_verdict_claimed': False}
