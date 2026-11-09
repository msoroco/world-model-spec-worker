"""Exact copied-source and authored U-turn geometry request compatibility."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import CASE, CASES, FRAMES, PLAN, POLICIES, SOURCE, SOURCE_SHA, road, rows, sha


def topology(path):
    xml=ET.parse(path).getroot()
    roads={int(r.attrib["id"]):r for r in xml.findall("road")}
    if set(roads)!={403,404,405,406,407,408}:
        raise ValueError("Crossed-street regions changed")
    expected={403:(-100,0,0,80,-1),404:(-20,0,0,40,1),405:(20,0,0,80,-1),
              406:(0,-100,math.pi/2,80,-1),407:(0,-20,math.pi/2,40,1),408:(0,20,math.pi/2,80,-1)}
    for ident,(x,y,hdg,length,junction) in expected.items():
        item=roads[ident];geometry=item.find('./planView/geometry')
        if (int(item.attrib['junction'])!=junction or geometry is None or geometry.find('line') is None or
                any(abs(float(geometry.attrib[key])-value)>1e-8 for key,value in
                    [('x',x),('y',y),('hdg',hdg),('length',length)])):
            raise ValueError("Crossed-street geometry changed")
        for section, lane_ids in [('left',{1,2,3}),('right',{-1,-2,-3})]:
            lanes=item.findall('./lanes/laneSection/'+section+'/lane')
            if {int(lane.attrib['id']) for lane in lanes}!=lane_ids or any(
                    lane.attrib.get('type')!='driving' or
                    abs(float(lane.find('width').attrib['a'])-4)>1e-8 for lane in lanes):
                raise ValueError("Six-lane centerline corridor changed")
        if item.find('signals/signal') is not None:
            raise ValueError("Unexpected authored traffic signal")
    junction=xml.find('junction')
    if junction is None or junction.attrib.get('id')!='1' or \
            {(int(c.attrib['incomingRoad']),int(c.attrib['connectingRoad'])) for c in junction.findall('connection')}!={(403,404),(406,407)}:
        raise ValueError("Crossed-street junction changed")


def check(bundle):
    bundle=Path(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    suffix=cfg['case_id'].split('__')[-1];candidate=cfg['candidate_id']
    if suffix not in CASES or candidate not in POLICIES:
        raise ValueError("Unknown controlled case or candidate")
    if (bundle/'assignment-source.json').read_bytes()!=SOURCE.read_bytes() or \
            (bundle/'case-plan.json').read_bytes()!=PLAN.read_bytes() or sha(SOURCE)!=SOURCE_SHA:
        raise ValueError("Copied frozen source or plan changed")
    source=json.loads(SOURCE.read_text());speed,camera,dwell=POLICIES[candidate]
    if (cfg['assignment_id']!=CASE.name or cfg['assignment_sha256']!=SOURCE_SHA or
            cfg['case_plan_sha256']!=sha(PLAN) or cfg['source_text']!=source['law_record']['text'] or
            cfg['requested_turn_center_x_m']!=CASES[suffix] or
            cfg['requested_approach_speed_mps']!=speed or cfg['camera_policy']!=camera or
            cfg['pre_turn_dwell_s']!=dwell or cfg['rate_hz']!=20 or cfg['frames']!=FRAMES or
            cfg['ego_blueprint']!='vehicle.tesla.model3' or
            cfg['status']!='unselected_native_request' or cfg['original_native_observed'] is not False or
            cfg['legal_verdict'] is not None):
        raise ValueError("Source-bound candidate config changed")
    path=bundle/'district-crossroads.xodr'
    if path.read_text()!=road() or cfg['road_sha256']!=sha(path):
        raise ValueError("Authored road changed")
    topology(path)
    track=bundle/'requested-tracks.jsonl'
    observed=[json.loads(line) for line in track.read_text().splitlines()]
    if cfg['tracks_sha256']!=sha(track) or len(observed)!=FRAMES or observed!=rows(suffix,candidate):
        raise ValueError("Authored U-turn tracks changed")
    return {"case_id":cfg['case_id'],"candidate_id":candidate,"frames":FRAMES,
            "original_native_observed":False,"delivery_ready":False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    args=parser.parse_args();print(json.dumps(check(args.bundle)))
