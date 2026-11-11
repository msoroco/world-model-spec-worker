"""Independently audit the unintegrated counterclockwise first-exit geometry."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROAD=HERE/'ccw-right-exit-draft.xodr'
PROOF=HERE/'ccw-right-exit-draft-proof.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def close(a,b,tol=1e-7):return abs(a-b)<tol

def end(geometry):
    s=float(geometry.attrib['s']);x=float(geometry.attrib['x'])
    y=float(geometry.attrib['y']);heading=float(geometry.attrib['hdg'])
    length=float(geometry.attrib['length'])
    arc=geometry.find('arc')
    if arc is None:return (s+length,x+length*math.cos(heading),
                           y+length*math.sin(heading),heading)
    curvature=float(arc.attrib['curvature']);new=heading+curvature*length
    return (s+length,x+(math.sin(new)-math.sin(heading))/curvature,
            y-(math.cos(new)-math.cos(heading))/curvature,new)

def audit(path):
    root=ET.parse(path).getroot()
    roads={int(node.attrib['id']):node for node in root.findall('road')}
    if set(roads)!={20,21,22,23}:raise ValueError('CCW road inventory differs')
    starts={};ends={};turns={}
    for ident,node in roads.items():
        segments=node.findall('./planView/geometry')
        if len(segments)!=(2 if ident in (20,22) else 1):
            raise ValueError('CCW entry/exit connector geometry differs')
        starts[ident]=(float(segments[0].attrib['x']),
                       float(segments[0].attrib['y']),float(segments[0].attrib['hdg']))
        previous=None;curvatures=[]
        for segment in segments:
            if previous is not None and (not close(previous[0],float(segment.attrib['s'])) or
                not close(previous[1],float(segment.attrib['x'])) or
                not close(previous[2],float(segment.attrib['y'])) or
                not close(math.sin(previous[3]),math.sin(float(segment.attrib['hdg']))) or
                not close(math.cos(previous[3]),math.cos(float(segment.attrib['hdg'])))):
                raise ValueError('CCW composite connector is discontinuous')
            previous=end(segment)
            arc=segment.find('arc')
            if arc is not None:curvatures.append(float(arc.attrib['curvature']))
        if not close(previous[0],float(node.attrib['length'])):
            raise ValueError('CCW road length differs')
        ends[ident]=previous[1:]
        turns[ident]=curvatures
        if {int(lane.attrib['id']) for lane in node.findall('./lanes/laneSection/right/lane')}!={-1,-2}:
            raise ValueError('CCW two-lane geometry differs')
    for a,b in ((20,21),(21,22),(21,23),(23,21)):
        if not all(close(u,v) for u,v in zip(ends[a][:2],starts[b][:2])) or not (
            close(math.sin(ends[a][2]),math.sin(starts[b][2])) and
            close(math.cos(ends[a][2]),math.cos(starts[b][2]))):
            raise ValueError('CCW entry, exit or closed-loop connection differs')
    if (turns[20]!=[-1/12] or turns[21]!=[1/15] or
        turns[22]!=[-1/12] or turns[23]!=[1/15]):
        raise ValueError('CCW circulation/connector direction differs')
    junctions={int(node.attrib['id']):node for node in root.findall('junction')}
    expected={100:{(20,21),(23,21)},101:{(21,22),(21,23)}}
    if set(junctions)!=set(expected):raise ValueError('CCW junction inventory differs')
    for ident,pairs in expected.items():
        actual=set()
        for connection in junctions[ident].findall('connection'):
            actual.add((int(connection.attrib['incomingRoad']),
                        int(connection.attrib['connectingRoad'])))
            if {(int(link.attrib['from']),int(link.attrib['to']))
                for link in connection.findall('laneLink')}!={(-1,-1),(-2,-2)}:
                raise ValueError('CCW junction lane allocation differs')
        if actual!=pairs:raise ValueError('CCW junction connectivity differs')
    return {'road_ids':sorted(roads),'junction_ids':sorted(junctions),
            'counterclockwise_arc_ids':[21,23],
            'rightmost_lane_id':-2,'outer_radius_m':20.25}

proof=json.loads(PROOF.read_text())
if (proof['road_sha256']!=sha(ROAD) or
    proof['status']!='integrated_unselected_cpu_draft' or
    sha(HERE/'right-exit-road.xodr')!=sha(ROAD) or
    len(proof['cases'])!=8 or
    not proof['reference_right_lane_outer']):
    raise ValueError('CCW proposal receipt differs')
positive=audit(ROAD)
negative={}
with tempfile.TemporaryDirectory(prefix='c132497-ccw-audit-') as temporary:
    for kind in ('missing_loop','wrong_direction','broken_junction_lane'):
        tree=ET.parse(ROAD);root=tree.getroot()
        if kind=='missing_loop':
            root.remove(next(node for node in root.findall('road') if node.attrib['id']=='23'))
        elif kind=='wrong_direction':
            next(node for node in root.findall('road') if node.attrib['id']=='21').find(
                './planView/geometry/arc').attrib['curvature']=str(-1/15)
        else:
            root.find('./junction/connection/laneLink').attrib['to']='-3'
        path=Path(temporary)/(kind+'.xodr');tree.write(path,encoding='unicode')
        try:audit(path)
        except ValueError as error:negative[kind]=str(error)
        else:raise ValueError('Damaged CCW design accepted: '+kind)

receipt={'format':'c132497-independent-ccw-design-audit-v1',
         'status':'integrated_unselected_cpu_draft','passed':True,
         'road_sha256':sha(ROAD),'design_proof_sha256':sha(PROOF),
         'positive':positive,'negative':negative,
         'current_bundles_replaced':True,'native_map_verified':False,
         'delivery_ready':False}
path=HERE/'ccw-design-audit.json'
path.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'passed':True,'integrated_unselected_cpu_draft':True,
                  'negative_rejections':len(negative),'road_sha256':sha(ROAD)}))
