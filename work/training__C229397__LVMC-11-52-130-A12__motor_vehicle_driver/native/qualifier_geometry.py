"""Qualifier variant road proposal; Native readback remains authoritative."""
import xml.etree.ElementTree as ET

from geometry import CROSSWALK_RECT, check as base_check, open_drive as base_open_drive


TARGET_X = {case: -5.0 for case in (
    'traffic_conflict_near', 'law_compliance_near',
    'police_direction_near', 'device_direction_near')}


def open_drive(case):
    if case not in TARGET_X:
        raise ValueError('unknown qualifier case')
    root = ET.fromstring(base_open_drive())
    if case == 'device_direction_near':
        signals = root.find('road/signals')
        ET.SubElement(signals, 'signal', id='101', s='43', t='-1.75',
                      name='proposed-crosswalk-traffic-light', dynamic='yes',
                      orientation='+', zOffset='0', hOffset='0', pitch='0',
                      roll='0', type='1000001', subtype='-1', value='0',
                      unit='unknown', height='3', width='.5')
    return ET.tostring(root, encoding='unicode')


def check():
    base = base_check()
    for case in TARGET_X:
        root = ET.fromstring(open_drive(case))
        signals = root.findall('road/signals/signal')
        if len(signals) != (1 if case == 'device_direction_near' else 0):
            raise ValueError('qualifier device proposal differs')
    return {'passed': True, 'targets': TARGET_X,
            'crosswalk_rect_xyxy_m': CROSSWALK_RECT,
            'device_signal_proposal_id': '101',
            'native_device_spawn_unverified': True,
            'physical_acceptance_claimed': False}
