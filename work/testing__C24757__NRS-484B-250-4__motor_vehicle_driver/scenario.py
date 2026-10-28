"""Partition 04 authored geometry, cases and native-map source checks."""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / 'intersection-source.xodr'


def mode(law_id):
    return {'NRS-484B-127-1': 'following', 'NRS-484B-600-1e': 'absolute_speed',
            'NRS-484B-600-1c': 'posted_speed', 'NRS-484B-307-6a': 'yellow_red',
            'NRS-484B-250-4': 'inoperative_signal'}[law_id]


def lane_path(cfg):
    kind = cfg['mode']
    if kind == 'following':
        points = []
        for i in range(1301):
            x = -70.0+i
            t = max(0.0, min(1.0, (x-180)/50))
            y = -1.75 - 3.5*(3*t*t-2*t*t*t)
            points.append((x,y))
        return points
    if kind in ('absolute_speed', 'posted_speed'):
        return [(-70.0+i, -1.75) for i in range(1901)]
    return [(-70.0+i*.5,-1.75) for i in range(261)]


def other_path(cfg):
    if cfg['mode'] == 'following':
        return [(-70.0+i,-1.75) for i in range(1301)]
    return [(1.75,45.0-i*.5) for i in range(161)]


def build_xodr(law_id):
    kind = mode(law_id)
    root = ET.parse(SOURCE).getroot()
    root.find('header').set('name', 'partition04-'+kind)
    for objects in root.findall('.//objects'):
        objects.clear()
    for signals in root.findall('.//signals'):
        signals.clear()
    if kind in ('following','absolute_speed','posted_speed'):
        first = root.find('road')
        for child in list(root):
            if child.tag in ('road','junction') and child is not first:
                root.remove(child)
        first.set('length','2000')
        first.find('planView/geometry').set('length','2000')
        first.find('planView/geometry').set('x','-100')
        first.find('link').clear()
        if kind != 'following':
            right = first.find('lanes/laneSection/right')
            for lane in list(right):
                if lane.get('id') == '-2':right.remove(lane)
            left = first.find('lanes/laneSection/left')
            for lane in list(left):
                if lane.get('id') == '2':left.remove(lane)
        if kind == 'posted_speed':
            signals = first.find('signals')
            signal = ET.SubElement(signals,'signal',{'id':'2601','name':'SpeedLimit25','s':'180','t':'-4.8',
                'zOffset':'2','dynamic':'no','orientation':'+','country':'Germany','type':'274',
                'subtype':'-1','value':'25','unit':'mph','height':'0.8','width':'0.8','text':'25'})
            ET.SubElement(signal,'validity',{'fromLane':'-1','toLane':'-1'})
    else:
        if kind == 'yellow_red':
            root.find('road[@id="1"]/lanes/laneSection/left').clear()
        roads = [r for r in root.findall('road') if r.get('id') in ('1','2','3','4')]
        for index, road in enumerate(roads):
            signals = road.find('signals')
            signal = ET.SubElement(signals,'signal',{'id':str(3001+index),'name':'TrafficLight',
                's':'385','t':'-7.7','zOffset':'3','dynamic':'yes','orientation':'+',
                'country':'Germany','type':'1000001','subtype':'-1','value':'-1',
                'height':'1','width':'0.5','text':''})
            ET.SubElement(signal,'validity',{'fromLane':'-2','toLane':'-1'})
            if kind == 'inoperative_signal':
                ET.SubElement(road.find('objects'),'object',{'id':str(4001+index),'name':'StopLine',
                    'type':'roadMark','s':'389','t':'-3.5','zOffset':'.01','hdg':'1.57079632679',
                    'length':'7','width':'.35','height':'0','orientation':'none'})
    return ET.tostring(root,encoding='unicode')


def static_check(cfg, xodr):
    root=ET.fromstring(xodr)
    assert root.tag=='OpenDRIVE'
    roads=root.findall('road')
    assert len({r.get('id') for r in roads})==len(roads)
    assert all(float(r.get('length'))>0 and r.find('planView/geometry') is not None for r in roads)
    path=lane_path(cfg)
    assert len(path)>100 and all(math.dist(a,b)<=1.01 for a,b in zip(path,path[1:]))
    if cfg['mode'] in ('following','absolute_speed','posted_speed'):
        assert len(roads)==1 and float(roads[0].get('length'))>=2000
    else:
        assert len(roads)>=6 and len(root.findall('.//signals/signal'))==4
    if cfg['mode']=='posted_speed':
        signs=root.findall('.//signals/signal')
        assert len(signs)==1 and signs[0].get('value')=='25'
    if cfg['mode']=='inoperative_signal':
        assert len(root.findall('.//objects/object[@type="roadMark"]'))==4
    return {'roads':len(roads),'path_points':len(path),'mode':cfg['mode']}
