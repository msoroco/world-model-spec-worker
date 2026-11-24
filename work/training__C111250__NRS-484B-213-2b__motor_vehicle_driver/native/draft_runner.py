"""Source-shaped intersection/centerline controller request; Native run pending."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def phase_at(config, frame):
    if not 0 <= frame < 600:
        raise ValueError('frame outside 600-frame window')
    hits = [p for p in config['control_phases'] if p['first_frame'] <= frame <= p['last_frame']]
    if len(hits) != 1:
        raise ValueError('uncovered or overlapping controller phase')
    return hits[0]


def check(config, road_text):
    if (config['law_id'], config['cell_id'], config['actor']) != ('NRS-484B-213-2b', 'C111250', 'motor_vehicle_driver'):
        raise ValueError('wrong frozen assignment identity')
    suffix = config['case_id'].split('__')[-1]
    if config['case_id'] != config['selected_case_id'] or suffix not in ('probe_01', 'probe_02', 'probe_03'):
        raise ValueError('wrong exact draft case identity')
    if (config['duration_frames'], config['duration_s'], config['rate_hz']) != (600, 30, 20):
        raise ValueError('short or unsynchronized source window')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS or any(c['fps'] != 20 for c in config['cameras']):
        raise ValueError('four synchronized named cameras required')
    if config['road_directionality'] != 'two_way' or config['ego_lane_id'] != '-1' or config['opposing_lane_id'] != '1':
        raise ValueError('two-way centerline context required')
    road = ET.fromstring(road_text)
    if len(road.findall('junction')) != 1 or len(road.findall('road')) < 5:
        raise ValueError('actual intersection geometry missing')
    lanes = road.findall('.//laneSection/left/lane') + road.findall('.//laneSection/right/lane')
    if not {'-1', '1'}.issubset({lane.get('id') for lane in lanes}):
        raise ValueError('opposing two-way lanes missing')
    if config['one_way_highway'] or config['railroad_crossing_claimed']:
        raise ValueError('different statutory context claimed')
    if config['physical_verified'] is not False or config['legal_verdict'] is not None:
        raise ValueError('invented physical or legal result')
    targets = [phase_at(config, i)['target_lane_id'] for i in (0, 299, 450, 599)]
    expected = {
        'probe_01': ['-1', '-1', '-1', '-1'],
        'probe_02': ['-1', '1', '-1', '-1'],
        'probe_03': ['-1', '-1', '1', '-1'],
    }[suffix]
    if targets != expected:
        raise ValueError('case controller contrast changed')
    return {'frames': 600, 'rate_hz': 20, 'four_cameras': list(CAMERAS),
            'intersection_requested': True, 'two_way_requested': True,
            'physical_verified': False, 'legal_verdict': None}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise SystemExit('draft route request only; Native capture implementation pending')
    print(json.dumps(check(json.loads(Path('config.json').read_text()), Path('road.xodr').read_text())))
