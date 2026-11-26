"""Exact unselected crest route/controller request; CARLA execution pending."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

CAMERAS = ('overview','approach','reference_corner','driver_reference')


def phase_at(config, frame):
    if not 0 <= frame < 600:
        raise ValueError('frame outside 600-frame window')
    hits = [p for p in config['control_phases'] if p['first_frame'] <= frame <= p['last_frame']]
    if len(hits) != 1:
        raise ValueError('uncovered or overlapping controller phase')
    return hits[0]


def check(config, road_text):
    if config['law_id'] != 'NRS-484B-213-2a' or config['cell_id'] != 'C230259' or config['actor'] != 'motor_vehicle_driver':
        raise ValueError('wrong frozen assignment identity')
    suffix = config['case_id'].split('__')[-1]
    if config['case_id'] != config['selected_case_id'] or suffix not in ('probe_a','probe_b','curve_right','curve_left','one_way_crest','one_way_curve'):
        raise ValueError('wrong exact draft case identity')
    if (config['duration_frames'],config['duration_s'],config['rate_hz']) != (600,30,20):
        raise ValueError('short or unsynchronized source window')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS or any(c['fps'] != 20 for c in config['cameras']):
        raise ValueError('four synchronized named cameras required')
    one_way = suffix.startswith('one_way')
    if config['road_directionality'] != ('one_way' if one_way else 'two_way') or config['ego_lane_id'] != ('-2' if one_way else '-1'):
        raise ValueError('wrong road directionality or ego route')
    if not one_way and config['opposing_lane_id'] != '1':
        raise ValueError('two-way opposing-lane route required')
    root = ET.fromstring(road_text)
    lanes = root.findall('.//laneSection/left/lane') + root.findall('.//laneSection/right/lane')
    if sorted(l.get('id') for l in lanes) != (['-1','-2'] if one_way else ['-1','1']):
        raise ValueError('OpenDRIVE lane direction geometry missing')
    elevations = root.findall('.//elevationProfile/elevation')
    curve = suffix.endswith('curve') or suffix.startswith('curve')
    arcs = root.findall('.//planView/geometry/arc')
    if curve:
        if not arcs or not any(abs(float(a.get('curvature',0))) > 0 for a in arcs):
            raise ValueError('curve geometry missing')
    elif len(elevations) < 4 or not any(float(e.get('c',0)) < 0 for e in elevations):
        raise ValueError('crest elevation profile missing')
    if one_way:
        if config['other_vehicle']['route_direction'] != 'same' or config['other_vehicle']['lane_id'] != '-1':
            raise ValueError('one-way same-direction participant required')
    elif config['other_vehicle']['route_direction'] != 'opposing' or config['other_vehicle']['lane_id'] != '1':
        raise ValueError('opposing participant absent')
    if config['hazard_distance_legal_judgment'] is not None or config['physical_verified'] is not False:
        raise ValueError('invented physical or legal result')
    if [phase_at(config,i) for i in range(600)][-1]['last_frame'] != 599:
        raise ValueError('controller incomplete')
    targets = [phase_at(config,i)['target_lane_id'] for i in (0,299,599)]
    if suffix in ('probe_a','curve_right') and targets != ['-1','-1','-1']:
        raise ValueError('right-side probe controller changed')
    expected_left_lane = '-1' if one_way else '1'
    expected_base_lane = '-2' if one_way else '-1'
    if suffix in ('probe_b','curve_left','one_way_crest','one_way_curve') and targets != [expected_base_lane,expected_left_lane,expected_base_lane]:
        raise ValueError('left-side probe controller changed')
    return {'frames':600,'rate_hz':20,'four_cameras':list(CAMERAS),
            'road_directionality':config['road_directionality'],'geometry':'curve' if curve else 'crest',
            'physical_verified':False,'legal_verdict':None}

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    if not args.check:
        raise SystemExit('unselected diagnostic only; Native capture implementation pending')
    print(json.dumps(check(json.loads(Path('config.json').read_text()),Path('road.xodr').read_text())))
