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
    if config['case_id'] != config['selected_case_id'] or config['case_id'].split('__')[-1] not in ('probe_a','probe_b'):
        raise ValueError('wrong exact draft case identity')
    if (config['duration_frames'],config['duration_s'],config['rate_hz']) != (600,30,20):
        raise ValueError('short or unsynchronized source window')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS or any(c['fps'] != 20 for c in config['cameras']):
        raise ValueError('four synchronized named cameras required')
    if config['road_directionality'] != 'two_way' or config['ego_lane_id'] != '-1' or config['opposing_lane_id'] != '1':
        raise ValueError('two-way opposing-lane route required')
    root = ET.fromstring(road_text)
    lanes = root.findall('.//laneSection/left/lane') + root.findall('.//laneSection/right/lane')
    if sorted(l.get('id') for l in lanes) != ['-1','1']:
        raise ValueError('two-sided OpenDRIVE lane geometry missing')
    elevations = root.findall('.//elevationProfile/elevation')
    if len(elevations) < 4 or not any(float(e.get('c',0)) < 0 for e in elevations):
        raise ValueError('crest elevation profile missing')
    if config['other_vehicle']['route_direction'] != 'opposing' or config['other_vehicle']['lane_id'] != '1':
        raise ValueError('opposing participant absent')
    if config['hazard_distance_legal_judgment'] is not None or config['physical_verified'] is not False:
        raise ValueError('invented physical or legal result')
    if [phase_at(config,i) for i in range(600)][-1]['last_frame'] != 599:
        raise ValueError('controller incomplete')
    targets = [phase_at(config,i)['target_lane_id'] for i in (0,299,599)]
    if config['case_id'].endswith('probe_a') and targets != ['-1','-1','-1']:
        raise ValueError('right-side probe controller changed')
    if config['case_id'].endswith('probe_b') and targets != ['-1','1','-1']:
        raise ValueError('left-side probe controller changed')
    return {'frames':600,'rate_hz':20,'four_cameras':list(CAMERAS),
            'road_directionality':'two_way','crest_requested':True,
            'physical_verified':False,'legal_verdict':None}

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    if not args.check:
        raise SystemExit('unselected diagnostic only; Native capture implementation pending')
    print(json.dumps(check(json.loads(Path('config.json').read_text()),Path('road.xodr').read_text())))
