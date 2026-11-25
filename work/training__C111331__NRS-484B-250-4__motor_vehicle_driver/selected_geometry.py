"""Author the marked-line, all-entrance Native signal intersection.

OpenDRIVE objects and signals are construction proposals. Native import must
read back their geometry and actual TrafficLight actors before delivery.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'current-v2-primary-sources/road.xodr'
APPROACHES = (('250', '701', 'eastbound'), ('253', '702', 'northbound'))


def build():
    root = ET.parse(SOURCE).getroot()
    root.find('header').set('name', 'C111331 all-entrance inoperative signal proposal')
    for road_id, signal_id, direction in APPROACHES:
        road = next(row for row in root.findall('road') if row.get('id') == road_id)
        if road.get('junction') != '-1' or float(road.get('length')) != 40:
            raise ValueError('Approach topology differs')
        if road.findall('./objects/object') or road.findall('./signals/signal'):
            raise ValueError('Expected undecorated source approach')
        objects = road.find('objects')
        ET.SubElement(objects, 'object', id=signal_id + '1',
                      name=direction + '-marked-stop-line', type='roadMark',
                      s='34', t='0', zOffset='0', hdg='0',
                      length='0.2', width='7', height='0')
        ET.SubElement(objects, 'object', id=signal_id + '2',
                      name=direction + '-near-side-crosswalk', type='crosswalk',
                      s='37', t='0', zOffset='0', hdg='0',
                      length='2', width='7', height='0')
        ET.SubElement(road.find('signals'), 'signal', id=signal_id,
                      name=direction + '-uncovered-vehicular-head', s='35',
                      t='-3.5', zOffset='4', hOffset='0', pitch='0', roll='0',
                      orientation='+', dynamic='yes', country='US',
                      type='1000001', subtype='0', value='0', unit='')
    return ET.tostring(root, encoding='unicode') + '\n'


def check(text):
    root = ET.fromstring(text)
    assert {s.get('id') for s in root.findall('.//signal')} == {'701', '702'}
    for road_id, signal_id, _ in APPROACHES:
        road = next(row for row in root.findall('road') if row.get('id') == road_id)
        assert road.find('signals/signal').get('id') == signal_id
        line, crossing = road.findall('./objects/object')
        assert line.get('type') == 'roadMark' and crossing.get('type') == 'crosswalk'
        assert float(line.get('s')) < float(crossing.get('s')) < float(road.get('length'))
        assert road.find('./lanes/laneSection/right/lane').get('id') == '-1'
    assert len(root.findall('junction/connection/laneLink')) >= 2
    return {'approaches': 2, 'signals_authored': 2, 'marked_lines_authored': 2,
            'crosswalks_authored': 2, 'native_signal_readback_observed': False,
            'physical_signal_off_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    value = build()
    check(value)
    Path(args.output).write_text(value)
