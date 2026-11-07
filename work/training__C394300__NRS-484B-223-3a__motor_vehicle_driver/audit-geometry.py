"""Independent audit of the saved 3(a) authored map and comparison routes."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def verify(xml_text, first, second):
    root=ET.fromstring(xml_text)
    roads={int(r.get('id')):r for r in root.findall('road')}
    assert set(roads)=={1,2,4,13,14,23,24}
    for ident in (1,14,2):
        lane=roads[ident].find("./lanes/laneSection/right/lane[@id='-1']")
        assert lane is not None and lane.get('type')=='bidirectional'
        assert lane.find("userData[@code='lane_use']").get('value')=='left_turn_only_both_directions'
        assert float(lane.find('width').get('a'))==3.5
        through=roads[ident].find("./lanes/laneSection/right/lane[@id='-2']")
        assert through is not None and through.get('type')=='driving'
    for ident in (13,23):
        geom=roads[ident].find('./planView/geometry')
        assert math.isclose(float(geom.get('length')),5.25*math.pi/2,abs_tol=1e-9)
        assert math.isclose(float(geom.find('arc').get('curvature')),1/5.25,abs_tol=1e-9)
    for connector,prior,next_road in ((13,1,4),(14,1,2),(23,2,24)):
        link=roads[connector].find('link')
        assert link.find('predecessor').get('elementId')==str(prior)
        assert link.find('successor').get('elementId')==str(next_road)
    links={(int(j.get('id')),int(c.get('incomingRoad')),int(c.get('connectingRoad')),
            int(l.get('from')),int(l.get('to')))
           for j in root.findall('junction') for c in j.findall('connection')
           for l in c.findall('laneLink')}
    assert links=={(100,1,13,-1,-1),(100,1,14,-1,-1),(200,2,23,-2,-1)}
    assert len(first)==1401 and len(second)==1901
    assert first[:851]==second[:851]
    for points in (first,second):
        assert all(len(p)==2 and all(math.isfinite(v) for v in p) for p in points)
        assert max(math.dist(a,b) for a,b in zip(points,points[1:]))<0.16
        assert points[0]==[-95,-3.5] and points[850]==[-10,0]
    assert first[1000]==[-3,7] and first[-1]==[-3,47]
    assert second[1000]==[5,0] and second[1350]==[40,-3.5]
    assert second[1500]==[47,3.5] and second[-1]==[47,43.5]
    assert all(abs(y)<1e-8 for x,y in second[851:1151])
    assert all(abs(y+3.5)<1e-8 for x,y in second[1251:1351])
    return {'passed':True,'first_opportunity_center_lane_through_m':30.0,
            'later_through_lane_before_turn_m':10.0,
            'first_exit_center_m':[-3,7],'second_exit_center_m':[47,3.5],
            'physical_or_driver_purpose_verified':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    base=args.directory
    xml=(base/'scene.xodr').read_text()
    first=json.loads((base/'route-controlled_1.json').read_text())
    second=json.loads((base/'route-controlled_2.json').read_text())
    result=verify(xml,first,second)
    changed=xml.replace('type="bidirectional"','type="driving"',1)
    try:verify(changed,first,second)
    except AssertionError:result['wrong_lane_type_rejected']=True
    else:raise AssertionError('Wrong center lane type was accepted')
    changed=json.loads(json.dumps(second));changed[1000][1]=-3.5
    try:verify(xml,first,changed)
    except AssertionError:result['wrong_through_path_rejected']=True
    else:raise AssertionError('Wrong comparison path was accepted')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
