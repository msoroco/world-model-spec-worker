"""CPU-authored same-direction emergency approach for NRS 484B.267(1)(a).

The paths are requests, not observed behavior. In particular, distance alone
does not establish when an approach is legally immediate, and a proposed
flashing lamp does not establish equipment qualification or vehicle authority.
"""
import json
import xml.etree.ElementTree as ET

RATE_HZ = 20
DURATION_S = 24
CASES = ('witness_1', 'witness_2')
ROAD_LENGTH_M = 260
LANE_WIDTH_M = 3.5


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C405647-1a-approach',
                  version='1', date='2026-11-06', north='20', south='-20',
                  east='220', west='-40', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='eastbound_approach',
                         length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-40', y='0', hdg='0', length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(LANE_WIDTH_M), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def _ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def requested_tracks(case, *, approach_start_x_m=-20, subject_speed_mps=3,
                     lane_change_start_s=2, lane_change_duration_s=3):
    """Return paired 20 Hz requests with common initial state and lamp plan."""
    if case not in CASES:
        raise ValueError('Unknown approach comparison case')
    if approach_start_x_m not in (-20, -10) or subject_speed_mps not in (3, 2.5):
        raise ValueError('Unknown approach construction')
    if (lane_change_start_s, lane_change_duration_s) not in ((2, 3), (1, 3)):
        raise ValueError('Unknown subject clearance construction')
    rows = []
    for frame in range(DURATION_S * RATE_HZ):
        time_s = frame / RATE_HZ
        emergency_x = approach_start_x_m + 8 * time_s
        subject_x = 30 + subject_speed_mps * time_s
        # The requested yielding path clears the inner lane before the
        # emergency reaches the subject's longitudinal position. The paired
        # conflicting-course request retains the inner lane.
        subject_y = -1.75 - (3.5 * _ease((time_s - lane_change_start_s) /
                                       lane_change_duration_s)
                                   if case == 'witness_1' else 0)
        rows.append({'frame': frame, 'time_s': round(time_s, 4),
                     'subject_request': {'x_m': round(subject_x, 4),
                                         'y_m': round(subject_y, 4)},
                     'approach_request': {'x_m': round(emergency_x, 4),
                                          'y_m': -1.75},
                     'lamp_request': {'front_red_flash_on': frame % 10 < 5,
                                      'period_s': 0.5},
                     'source_kind': 'authored_cpu_request'})
    return rows


def native_track_requests(case, **knobs):
    """Reflect authored OpenDRIVE y for proposed CARLA world coordinates."""
    rows = []
    for row in requested_tracks(case, **knobs):
        copied = {**row, 'subject_request': dict(row['subject_request']),
                  'approach_request': dict(row['approach_request']),
                  'source_kind': 'authored_native_request'}
        copied['subject_request']['y_m'] *= -1
        copied['approach_request']['y_m'] *= -1
        rows.append(copied)
    return rows


def check():
    root = ET.fromstring(open_drive())
    road = root.find("./road[@id='1']")
    assert road is not None and float(road.attrib['length']) == ROAD_LENGTH_M
    assert [lane.attrib['id'] for lane in road.findall('./lanes/laneSection/right/lane')] == ['-1', '-2']
    first, second = (requested_tracks(case) for case in CASES)
    assert len(first) == len(second) == DURATION_S * RATE_HZ
    assert first[0]['subject_request'] == second[0]['subject_request']
    assert all(a['approach_request'] == b['approach_request'] and
               a['lamp_request'] == b['lamp_request'] for a, b in zip(first, second))
    assert first[100]['subject_request']['y_m'] == -5.25
    assert second[100]['subject_request']['y_m'] == -1.75
    assert all(row['source_kind'] == 'authored_cpu_request' for row in first + second)
    native = native_track_requests('witness_1')
    assert len(native) == len(first)
    assert all(a['subject_request']['y_m'] == -b['subject_request']['y_m'] and
               a['approach_request']['y_m'] == -b['approach_request']['y_m']
               for a, b in zip(first, native))
    return {'passed': True, 'frames_per_case': len(first),
            'case_ids': list(CASES), 'fixed_approach_and_lamp_request': True,
            'physical_lamp_authority_or_immediacy_verified': False,
            'native_y_reflection_request_checked': True,
            'scope': 'CPU-authored OpenDRIVE and paired actor requests only'}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
