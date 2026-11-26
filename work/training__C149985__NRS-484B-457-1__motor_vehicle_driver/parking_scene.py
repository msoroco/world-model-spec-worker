"""One-way parking construction requests; authority is deliberately unverified."""

import xml.etree.ElementTree as ET

CASES = {
    'right_16_parked': ('default_right', 16, 0, 'parked'),
    'right_18_parked': ('default_right', 18, 0, 'parked'),
    'right_20_parked': ('default_right', 20, 0, 'parked'),
    'right_18_stopped': ('default_right', 18, 0, 'stopped'),
    'left_18_ordinance': ('left_ordinance', 18, 0, 'parked'),
    'angle_ordinary': ('angle_ordinary', 18, 45, 'parked'),
    'angle_dot': ('angle_dot', 18, 45, 'parked'),
}

CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def road_xml(kind):
    if kind not in {'default_right', 'left_ordinance', 'angle_ordinary', 'angle_dot'}:
        raise ValueError('Unknown parking kind')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C149985-one-way-parking',
                  version='1', north='2', south='-10', east='80', west='-80', vendor='worker')
    road = ET.SubElement(root, 'road', id='149985', name='one_way_curbed_highway', length='160', junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-80', y='0', hdg='0', length='160')
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    lane = ET.SubElement(left, 'lane', id='1', type='shoulder', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='2', b='0', c='0', d='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, lane_type, width in ((-1, 'driving', 4), (-2, 'driving', 4), (-3, 'shoulder', 2)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=lane_type, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
    objects = ET.SubElement(road, 'objects')
    for name, t in (('left_curb', 2), ('right_curb', -10)):
        ET.SubElement(objects, 'object', id=name, s='0', t=str(t), name=name,
                      type='curb', orientation='none', zOffset='0', length='160',
                      width='.15', hdg='0', pitch='0', roll='0')
    signals = ET.SubElement(road, 'signals')
    if kind != 'default_right':
        name = 'left_side_parking_notice' if kind == 'left_ordinance' else 'angle_parking_notice'
        ET.SubElement(signals, 'signal', id='457', s='70', t='1.8' if kind == 'left_ordinance' else '-9.8',
                      name=name, type='parking', subtype='notice', orientation='+',
                      dynamic='no', zOffset='0', hOffset='0', value='0', unit='')
    return ET.tostring(root, encoding='unicode')


def request(case_id):
    if case_id not in CASES:
        raise ValueError('Unknown exact parking case')
    kind, gap_in, yaw, rest_mode = CASES[case_id]
    curb_y = 2 if kind == 'left_ordinance' else -10
    center_y = curb_y - .8 - gap_in * .0254 if kind == 'left_ordinance' else curb_y + .8 + gap_in * .0254
    return {'format': 'worker-c149985-selected-request', 'case': case_id,
            'parking_kind': kind, 'rest_mode': rest_mode, 'requested_gap_in': gap_in,
            'requested_heading_deg': yaw, 'requested_center_xy_m': [0, center_y],
            'source_map': road_xml(kind), 'right_curb_y_m': -10, 'left_curb_y_m': 2,
            'roadway_lanes': {'same_direction_driving': [-1, -2],
                              'parking_shoulders': [1, -3]},
            'authority_request': {'local_ordinance': kind != 'default_right',
                                  'dot_width_determination': kind == 'angle_dot',
                                  'original_authority_verified': False},
            'rate_hz': 20, 'frames': 600, 'duration_s': 30,
            'cameras': [{'name': name, 'width': width, 'height': height}
                        for name, width, height in CAMERAS],
            'native_observed': False, 'physical_completion_claimed': False}


def check(value):
    root = ET.fromstring(value['source_map'])
    road = root.find('road')
    if road is None or road.attrib.get('id') != '149985':
        raise ValueError('Exact road missing')
    lanes = road.findall('.//lane')
    driving = {int(l.attrib['id']) for l in lanes if l.attrib.get('type') == 'driving'}
    if driving != {-1, -2}:
        raise ValueError('One-way lane directions not established')
    objects = {x.attrib.get('name') for x in road.findall('./objects/object')}
    if objects != {'left_curb', 'right_curb'}:
        raise ValueError('Two curb surfaces missing')
    if value['frames'] != 600 or value['rate_hz'] != 20 or value['duration_s'] != 30:
        raise ValueError('Exact capture duration missing')
    if [(c['name'], c['width'], c['height']) for c in value['cameras']] != list(CAMERAS):
        raise ValueError('Four camera profile missing')
    if value['authority_request']['original_authority_verified'] or value['native_observed']:
        raise ValueError('Unobserved authority or Native state claimed')
    return {'passed': True, 'case': value['case'], 'one_way_lanes': sorted(driving),
            'source_authority_pending': value['authority_request']['local_ordinance'],
            'physical_completion_claimed': False}
