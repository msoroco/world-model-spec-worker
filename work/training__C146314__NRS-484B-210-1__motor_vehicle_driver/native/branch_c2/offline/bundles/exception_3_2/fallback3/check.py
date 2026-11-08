"""Preflight copied paragraph (c)(2) private-way requests without legal claims."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import SOURCE, START_X, EXIT_X, PRIVATE_WAY_X, POLICIES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(bundle):
    bundle = Path(bundle)
    cfg = read(bundle/'config.json')
    plan = read(bundle/'case-plan.json')
    assignment = read(bundle/'assignment-source.json')
    source = plan['source_law']['text']
    require(source == assignment['law_record']['text'] and
            hashlib.sha256(source.encode()).hexdigest() ==
            '525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a' and
            SOURCE in source and 'not marked as a traffic lane; or (2)' in source,
            'frozen disjunctive paragraph (c) source')
    witness = cfg['case_id'].split('__')[-1]
    candidate = cfg['candidate_id']
    require(witness in ('exception_3_1', 'exception_3_2') and
            candidate in POLICIES, 'c2 witness/candidate')
    private_way = witness == 'exception_3_1'
    speed, camera, stop = POLICIES[candidate]
    road = ET.parse(bundle/'unmarked-pass.xodr').getroot()
    roads = road.findall('./road')
    main = next((x for x in roads if x.attrib.get('id') == '212'), None)
    spur = next((x for x in roads if x.attrib.get('id') == '214'), None)
    main_geometry = main.find('./planView/geometry') if main is not None else None
    require(main is not None and len(roads) == (2 if private_way else 1) and
            (spur is not None) == private_way and
            main_geometry is not None and
            all(math.isclose(float(main_geometry.attrib[k]), v) for k, v in
                (('x', 0), ('y', 0), ('hdg', 0), ('length', 300))) and
            [(int(x.attrib['id']), x.attrib['type']) for x in
             main.findall('./lanes/laneSection/right/lane')] ==
                [(-1, 'driving'), (-2, 'shoulder')] and
            main.find('./lanes/laneSection/right/lane[@id="-2"]/roadMark').attrib['type'] == 'none',
            'authored unmarked highway and private-way road count')
    if private_way:
        geometry = spur.find('./planView/geometry')
        junction = road.find('./junction')
        connection = junction.find('./connection') if junction is not None else None
        require(geometry is not None and
                math.isclose(float(geometry.attrib['x']), PRIVATE_WAY_X) and
                math.isclose(float(geometry.attrib['y']), -3.5) and
                math.isclose(float(geometry.attrib['hdg']), -math.pi/2) and
                connection is not None and
                connection.attrib['incomingRoad'] == '212' and
                connection.attrib['connectingRoad'] == '214' and
                connection.find('./laneLink').attrib == {'from': '-1', 'to': '-1'},
                'private-way spur and junction topology')
    else:
        require(road.find('./junction') is None, 'unexpected private way')
    track = rows(bundle/'requested-tracks.jsonl')
    require(cfg['format'] == 'c146314-paragraph-c2-request-v1' and
            cfg['assignment_sha256'] == sha(bundle/'assignment-source.json') and
            cfg['case_plan_sha256'] == sha(bundle/'case-plan.json') and
            cfg['road_sha256'] == sha(bundle/'unmarked-pass.xodr') and
            cfg['tracks_sha256'] == sha(bundle/'requested-tracks.jsonl') and
            cfg['source_branch'] == 'NRS 484B.210(1)(c)(2)' and
            cfg['private_way_requested'] is private_way and
            cfg['requested_c2_no_private_way_passed'] is (not private_way) and
            cfg['requested_c1_over_200ft'] is True and
            cfg['requested_ego_speed_mps'] == speed and
            cfg['camera_policy'] == camera and cfg['stop_x_m'] == stop and
            cfg['unmarked_segment_start_x_m'] == START_X and
            cfg['unmarked_segment_end_x_m'] == EXIT_X and
            cfg['private_way_x_m'] == PRIVATE_WAY_X and
            cfg['rate_hz'] == 20 and cfg['frames'] == len(track) == 240 and
            cfg['status'] == 'unselected_native_request' and
            all(cfg[k] is False for k in
                ('actual_private_way_passed_observed',
                 'actual_unmarked_distance_observed',
                 'actual_right_pass_observed', 'original_native_observed')),
            'source-bound c2 candidate')
    pass_frames = spur_zone_frames = 0
    for i, row in enumerate(track):
        t = (i+1)/20
        x = min(stop or 300, 5+speed*t)
        blend = max(0, min(1, (x-(START_X-3.8))/5,
                           (EXIT_X+3.8-x)/5))
        require(row['frame'] == i and row['time_s'] == t and
                row['source_kind'] == 'authored_native_request' and
                row['source_branch'] == cfg['source_branch'] and
                row['case_id'] == cfg['case_id'] and
                row['candidate_id'] == candidate and row['road_id'] == 212 and
                math.isclose(row['ego_x_m'], x, abs_tol=1e-6) and
                math.isclose(row['ego_y_m'], -1.75-3.5*blend, abs_tol=1e-6) and
                math.isclose(row['lead_x_m'], 30+4*t, abs_tol=1e-6) and
                row['lead_y_m'] == -1.75 and
                row['private_way_x_m'] == PRIVATE_WAY_X and
                row['private_way_requested'] is private_way and
                row['requested_c2_no_private_way_passed'] is (not private_way) and
                row['requested_c1_over_200ft'] is True and
                all(row[k] is False for k in
                    ('actual_private_way_passed_observed',
                     'actual_unmarked_distance_observed',
                     'actual_right_pass_observed',
                     'pavement_unobstructed_verified',
                     'no_parked_vehicles_verified')) and
                row['legal_verdict'] is None,
                f'authored private-way frame {i}')
        pass_frames += int(x > row['lead_x_m'] and blend >= .99)
        spur_zone_frames += int(abs(x-PRIVATE_WAY_X) <= 2 and blend >= .99)
    require((pass_frames == 0) == (stop is not None) and
            (spur_zone_frames == 0) == (stop is not None),
            'pass/spur-zone request split')
    return {'case_id': cfg['case_id'], 'candidate_id': candidate,
            'private_way_requested': private_way,
            'requested_c2_no_private_way_passed': not private_way,
            'requested_c1_over_200ft': True,
            'requested_right_ahead_frames': pass_frames,
            'requested_spur_zone_frames': spur_zone_frames,
            'actual_private_way_passed_observed': False,
            'original_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    print(json.dumps(check(p.parse_args().bundle)))
