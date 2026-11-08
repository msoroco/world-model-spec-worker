"""Independent structural audit of all authored C102951 Native requests."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
AID = CASE.name
DISTANCES = (70, 120, 170)
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elevation(node, s):
    u = s-float(node.attrib['s'])
    return sum(float(node.attrib[k])*u**power for power, k in enumerate('abcd'))


def audit():
    manifest = json.loads((HERE/'drafts/manifest.json').read_text())
    assignment = ROOT/'inputs'/AID/'assignment.json'
    plan = CASE/'case-plan.json'
    road = HERE/'road.xodr'
    if (manifest['assignment_sha256'], manifest['case_plan_sha256'], manifest['road_sha256']) != (sha(assignment), sha(plan), sha(road)):
        raise ValueError('Frozen or authored construction hash differs')
    if manifest['original_native_observed'] or manifest['delivery_ready'] or manifest['highway_status_reviewed']:
        raise ValueError('Authored request claims observed or ready status')
    tree = ET.parse(road)
    roads = tree.findall('.//road')
    if len(roads) != 1 or roads[0].attrib['id'] != '1' or float(roads[0].attrib['length']) != 800:
        raise ValueError('Two-way road envelope differs')
    geometry = tree.find('.//planView/geometry')
    if float(geometry.attrib['x']) != -200 or float(geometry.attrib['length']) != 800:
        raise ValueError('Road geometry does not contain all traffic')
    lanes = {int(l.attrib['id']): l.attrib['type'] for l in tree.findall('.//lane')}
    if lanes != {-1: 'driving', 0: 'none', 1: 'driving'}:
        raise ValueError('Exactly two opposing driving lanes required')
    pieces = tree.findall('.//elevationProfile/elevation')
    if [float(p.attrib['s']) for p in pieces] != [0, 200, 350, 500]:
        raise ValueError('Crest profile stations differ')
    if abs(elevation(pieces[1], 350)-1.5) > 1e-6 or abs(elevation(pieces[2], 500)) > 1e-6:
        raise ValueError('Authored crest discontinuity')
    entries = manifest['entries']
    if len(entries) != 12 or {(e['case_id'], e['candidate_id']) for e in entries} != {
            (AID+'__'+str(d), c) for d in DISTANCES for c in CANDIDATES}:
        raise ValueError('Three-case four-candidate coverage differs')
    policies = {}
    for entry in entries:
        folder = (CASE/entry['config']).parent
        config = json.loads((folder/'config.json').read_text())
        track = folder/'requested-tracks.jsonl'
        if (config['case_id'], config['candidate_id'], config['status']) != (
                entry['case_id'], entry['candidate_id'], 'unselected_native_request'):
            raise ValueError('Candidate identity or status differs')
        if (config['assignment_sha256'], config['case_plan_sha256'], config['road_sha256'], config['tracks_sha256']) != (
                sha(assignment), sha(plan), sha(road), sha(track)):
            raise ValueError('Candidate source hash differs')
        distance = config['distance_m']
        if distance not in DISTANCES or entry['case_id'] != AID+'__'+str(distance):
            raise ValueError('Frozen sweep case differs')
        policy = config['policy']
        policies.setdefault(entry['candidate_id'], policy)
        if policies[entry['candidate_id']] != policy:
            raise ValueError('Policy changes between sweep probes')
        rows = [json.loads(line) for line in track.read_text().splitlines()]
        if len(rows) != 480:
            raise ValueError('24-second Native request incomplete')
        for i, row in enumerate(rows):
            if (row['frame'] != i or abs(row['time_s']-i/20) > 1e-6 or
                    row['source_kind'] != 'authored_native_request' or
                    row['ego_blueprint_request'] != 'vehicle.tesla.model3' or
                    row['requested_entry_oncoming_body_gap_m'] != distance or
                    row['requested_driver_eye_clear_m'] != distance or
                    row['sightline_assumed_visible'] is not True):
                raise ValueError('Frame, time or requested observation differs')
            x, y = row['ego_center_xy_m']
            ox, oy = row['overtaken_center_xy_m']
            ax, ay = row['oncoming_center_xy_m']
            if (not all(math.isfinite(v) and -200 <= v <= 600 for v in (x, ox, ax)) or
                    oy != -1.75 or ay != 1.75 or not -1.75 <= y <= 1.75 or
                    row['overtaken_speed_mps'] != 8 or row['oncoming_speed_mps'] != 12 or
                    row['ego_speed_mps'] != policy['ego_speed_mps']):
                raise ValueError('Actor request or road envelope differs')
            if i and (abs(x-rows[i-1]['ego_center_xy_m'][0]-policy['ego_speed_mps']/20) > 1e-3 or
                      abs(ox-rows[i-1]['overtaken_center_xy_m'][0]-.4) > 1e-3 or
                      abs(ax-rows[i-1]['oncoming_center_xy_m'][0]+.6) > 1e-3):
                raise ValueError('Actor speed and track differ')
        left = [i for i, r in enumerate(rows) if r['ego_center_xy_m'][1]+.9 > 0]
        if not left:
            raise ValueError('Left-of-center request absent')
        first = rows[left[0]]
        gap = first['oncoming_center_xy_m'][0]-first['ego_center_xy_m'][0]-4.4
        if abs(gap-distance) > 1e-3:
            raise ValueError('Entry oncoming gap differs from requested probe')
        if not any(r['ego_center_xy_m'][1] == -1.75 for r in rows[left[-1]+1:]):
            raise ValueError('Rejoin request absent')
    if len({json.dumps(p, sort_keys=True) for p in policies.values()}) != 4:
        raise ValueError('Fallback policies are not distinct')
    if policies['fallback3']['mode'] != 'abort_and_rejoin':
        raise ValueError('Abort fallback absent')
    receipt = {'format': 'c102951-native-construction-audit-v1',
               'assignment_id': AID, 'road_sha256': sha(road),
               'manifest_sha256': sha(HERE/'drafts/manifest.json'),
               'case_count': 3, 'candidate_count_per_case': 4,
               'request_frame_rows': 5760,
               'original_native_observed': False,
               'physical_or_legal_result_claimed': False,
               'delivery_ready': False}
    (HERE/'construction-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
