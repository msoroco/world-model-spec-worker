"""Same-shoulder/oncoming lamp-use signal requests; official status unverified."""
import xml.etree.ElementTree as ET

import beam_scene as base


SIGN_ID = '100'
SIGN_NAME = 'AUTHORED_LAMP_USE_INSTRUCTION'
MODES = {'device_dim': 'dim_within_500', 'device_high': 'retain_high'}
CAMERAS = base.CAMERAS
beam_request = base.beam_request


def road_opendrive():
    root = ET.fromstring(base.road_opendrive())
    signals = root.find('road/signals')
    if signals is None:
        raise ValueError('Device road has no signal container')
    ET.SubElement(signals, 'signal', id=SIGN_ID, s='160', t='-6',
                  name=SIGN_NAME, dynamic='no', orientation='+',
                  zOffset='2', country='USA', type='lamp_use_instruction',
                  subtype='headlamps', value='0', unit='none',
                  hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def request(case):
    if case not in MODES:
        raise ValueError('Unknown device comparison case')
    plan = base.request('condition_a' if case == 'device_dim' else 'condition_b')
    plan['case'] = case
    plan['beam_mode'] = MODES[case]
    plan['road_opendrive'] = road_opendrive()
    plan['device_request'] = {'signal_id': SIGN_ID, 'signal_name': SIGN_NAME,
                              'directive': 'use_lamps',
                              'official_authority_verified': False,
                              'ego_applicability_verified': False}
    plan['lighting']['trigger_evidence'] = 'Original signal placement/state and independent official-authority review required'
    return plan


def validate_request(plan):
    base.validate_request(plan)
    case = plan['case']
    if case not in MODES or plan['beam_mode'] != MODES[case]:
        raise ValueError('Device pair identity differs')
    signal = ET.fromstring(plan['road_opendrive']).find('road/signals/signal')
    if signal is None or signal.attrib.get('id') != SIGN_ID or \
            signal.attrib.get('name') != SIGN_NAME or \
            signal.attrib.get('type') != 'lamp_use_instruction' or \
            signal.attrib.get('orientation') != '+':
        raise ValueError('Exact authored lamp-use signal missing')
    if plan.get('device_request') != {'signal_id': SIGN_ID, 'signal_name': SIGN_NAME,
                                     'directive': 'use_lamps',
                                     'official_authority_verified': False,
                                     'ego_applicability_verified': False}:
        raise ValueError('Authored device cannot assert official status')
    return {'case': case, 'signal_id': SIGN_ID, 'camera_count': 4,
            'frames': 600, 'official_status_verified': False}
