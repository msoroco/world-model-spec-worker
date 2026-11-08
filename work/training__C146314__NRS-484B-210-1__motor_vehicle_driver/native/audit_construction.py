"""Independent source and controlled-pair audit of C146314 request construction."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[1]
NATIVE = CASE / 'native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit():
    assignment_path = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan_path = CASE / 'case-plan.json'
    assignment, plan = read(assignment_path), read(plan_path)
    require(plan['source_law']['text'] == assignment['law_record']['text'] and
            plan['source_law']['source'] == assignment['law_record']['source'] and
            len(plan['source_law']['sha256']) == 64, 'exact frozen statute')
    require('Upon any highway on which traffic is restricted to one direction'
            in plan['source_law']['text'], 'paragraph d missing')
    require(plan['frozen_cell'] == {'layout': 'one_way_multilane',
            'maneuver': 'overtake_right', 'control': 'other_vehicle'}, 'cell')
    require(assignment['cell_id'] == 'C146314', 'frozen input')
    road_path = NATIVE / 'one-way-pass.xodr'
    root = ET.parse(road_path).getroot()
    road = root.find('road')
    require(road is not None and road.attrib['id'] == '210' and
            float(road.attrib['length']) == 300, 'road identity')
    require(road.find('planView/geometry/line') is not None, 'straight road')
    lanes = {int(l.attrib['id']): l for l in road.findall(
        'lanes/laneSection/right/lane')}
    require(set(lanes) == {-1, -2} and all(
        l.attrib['type'] == 'driving' and
        float(l.find('width').attrib['a']) == 3.5 for l in lanes.values()),
        'two driving lines')
    manifest = read(NATIVE / 'manifest.json')
    require(manifest['assignment_sha256'] == sha(assignment_path) and
            manifest['case_plan_sha256'] == sha(plan_path) and
            manifest['road_sha256'] == sha(road_path) and
            len(manifest['entries']) == 8 and
            manifest['original_native_observed'] is False and
            manifest['delivery_ready'] is False, 'manifest provenance')
    by_key = {}
    for entry in manifest['entries']:
        witness = entry['case_id'].split('__')[-1]
        candidate = entry['candidate_id']
        require(witness in ('witness_1', 'witness_2') and candidate in
                ('primary', 'fallback1', 'fallback2', 'fallback3'), 'candidate key')
        target = NATIVE / 'drafts' / witness / candidate
        cfg, track = read(target / 'config.json'), rows(target / 'requested-tracks.jsonl')
        require(cfg['assignment_sha256'] == sha(assignment_path) and
                cfg['case_plan_sha256'] == sha(plan_path) and
                cfg['road_sha256'] == sha(road_path) and
                cfg['tracks_sha256'] == sha(target / 'requested-tracks.jsonl') and
                entry['config_sha256'] == sha(target / 'config.json') and
                entry['tracks_sha256'] == cfg['tracks_sha256'], 'source hashes')
        require(cfg['status'] == entry['status'] == 'unselected_native_request' and
                not cfg['actual_right_pass_observed'] and
                not cfg['one_way_designation_verified'] and
                not cfg['original_native_observed'] and
                len(track) == 240, 'unselected request')
        assert cfg['right_lane_obstruction_requested'] == (witness == 'witness_2')
        require(cfg['obstruction_y_m'] == (-6.8 if witness == 'witness_2' else None)
                and cfg['obstruction_radius_m'] ==
                (0.2 if witness == 'witness_2' else None), 'object geometry')
        expected_speed = 7 if candidate == 'fallback1' else 8
        expected_stop = 45 if candidate == 'fallback3' else None
        expected_camera = 'elevated_overview' if candidate == 'fallback2' else 'standard'
        require((cfg['requested_ego_speed_mps'], cfg['stop_x_m'], cfg['camera_policy'])
                == (expected_speed, expected_stop, expected_camera), 'variant policy')
        for i, row in enumerate(track):
            t = (i + 1) / 20
            x = min(expected_stop or 300, expected_speed * t)
            right = max(0, min(1, (x - 15) / 20, (105 - x) / 20))
            require(row['frame'] == i and row['time_s'] == t and
                    row['road_id'] == 210 and row['source_kind'] ==
                    'authored_native_request' and
                    math.isclose(row['ego_x_m'], x, abs_tol=1e-6) and
                    math.isclose(row['ego_y_m'], -1.75 - 3.5*right,
                                 abs_tol=1e-6) and
                    math.isclose(row['lead_x_m'], 30 + 4*t, abs_tol=1e-6) and
                    row['lead_y_m'] == -1.75 and row['lead_lane_id'] == -1 and
                    row['right_lane_obstruction_requested'] ==
                    (witness == 'witness_2') and
                    row['obstruction_x_m'] ==
                    (55 if witness == 'witness_2' else None) and
                    row['obstruction_y_m'] ==
                    (-6.8 if witness == 'witness_2' else None) and
                    row['obstruction_radius_m'] ==
                    (0.2 if witness == 'witness_2' else None) and
                    not row['actual_right_pass_observed'] and
                    not row['one_way_designation_verified'] and
                    not row['unobstructed_pavement_verified'] and
                    row['legal_verdict'] is None, f'frame {i} source/geometry')
        by_key[witness, candidate] = track
    require(len(by_key) == 8, 'missing pair/candidate')
    comparisons = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a, b = by_key['witness_1', candidate], by_key['witness_2', candidate]
        fixed = ('frame', 'time_s', 'phase', 'road_id', 'ego_x_m', 'ego_y_m',
                 'ego_lane_id', 'lead_x_m', 'lead_y_m', 'lead_lane_id')
        require(all(all(x[k] == y[k] for k in fixed) for x, y in zip(a, b)),
                'controlled pass trace differs')
        requested_pass = sum(x['ego_x_m'] > x['lead_x_m'] and
                             x['ego_lane_id'] == -2 for x in a)
        obstruction_overlap = sum(x['right_lane_obstruction_requested'] and
                                  abs(x['ego_x_m']-55) < 3 and
                                  x['ego_lane_id'] == -2 for x in b)
        comparisons.append({'candidate_id': candidate,
                            'requested_right_ahead_frames': requested_pass,
                            'requested_obstruction_overlap_frames': obstruction_overlap,
                            'physical_clearance_verified': False})
    require(all(x['requested_right_ahead_frames'] > 0 for x in comparisons[:3])
            and comparisons[3]['requested_right_ahead_frames'] == 0 and
            all(x['requested_obstruction_overlap_frames'] > 0
                for x in comparisons[:3]) and
            comparisons[3]['requested_obstruction_overlap_frames'] == 0,
            'request split')
    proof = {'format': 'c146314-construction-audit-v1',
             'assignment_id': CASE.name, 'bundle_count': 8,
             'request_rows': 1920, 'comparisons': comparisons,
             'source_hashes_valid': True, 'original_native_observed': False,
             'physical_clearance_verified': False, 'delivery_ready': False}
    (NATIVE / 'construction-audit.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
