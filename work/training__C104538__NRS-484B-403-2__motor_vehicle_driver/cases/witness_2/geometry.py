"""Authored hill-crest, signed straight/U-turn Native construction seed.

CARLA reflects OpenDRIVE y for lane waypoints. Native routes below are the
reflected coordinates; the authored sign remains a proposal until map readback.
"""
import math
import xml.etree.ElementTree as ET

ROAD_LENGTH_M=160.0
LANE_WIDTH_M=8.0
NATIVE_APPROACH_Y_M=4.0
TURN_RADIUS_M=4.0


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C104538-signed-u-turn-draft',
                  version='1',date='2026-11-06',north='100',south='-100',
                  east='100',west='-100',vendor='full-train-worker')
    road=ET.SubElement(root,'road',id='1',name='hill_crest_signed_u_turn',
                       length=str(ROAD_LENGTH_M),junction='-1')
    ET.SubElement(road,'link')
    geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-80',y='0',
                           hdg='0',length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry,'line')
    profile=ET.SubElement(road,'elevationProfile')
    ET.SubElement(profile,'elevation',s='0',a='0',b='0.04',c='-0.00025',d='0')
    ET.SubElement(profile,'elevation',s='80',a='1.6',b='0',c='-0.00025',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    for side,lane_id in (('left',1),('right',-1)):
        lane=ET.SubElement(ET.SubElement(section,side),'lane',id=str(lane_id),
                           type='driving',level='false')
        ET.SubElement(lane,'width',sOffset='0',a=str(LANE_WIDTH_M),b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='white',width='0.12')
    center=ET.SubElement(section,'center')
    lane=ET.SubElement(center,'lane',id='0',type='none',level='false')
    ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='yellow',width='0.12')
    signals=ET.SubElement(road,'signals')
    ET.SubElement(signals,'signal',id='4032',name='no_u_turn_prohibition_proposal',
                  s='72',t='-6',zOffset='2.3',hOffset='0',pitch='0',roll='0',
                  orientation='+',dynamic='no',country='US',type='206',subtype='0',
                  value='0',unit='none')
    ET.SubElement(road,'objects')
    return ET.tostring(root,encoding='unicode')


def native_route(case_suffix,turn_radius_m=TURN_RADIUS_M):
    if case_suffix not in ('witness_1','witness_2'):
        raise ValueError('Unknown signed U-turn case')
    if not 3.9<=turn_radius_m<=4.1:
        raise ValueError('Turn radius would leave the opposite lane')
    approach=[[-50+i*.1,NATIVE_APPROACH_Y_M] for i in range(501)]
    if case_suffix=='witness_1':
        return approach+[[i*.1,NATIVE_APPROACH_Y_M] for i in range(1,501)]
    # A clockwise Native half circle reverses eastbound heading into the
    # opposite westbound lane. Authored OpenDRIVE y has the opposite sign.
    turn=[]
    for i in range(1,201):
        angle=math.pi/2-math.pi*i/200
        turn.append([turn_radius_m*math.cos(angle),turn_radius_m*math.sin(angle)])
    return approach+turn+[[-i*.1,-NATIVE_APPROACH_Y_M] for i in range(1,501)]


def authored_route(case_suffix):
    return [[x,-y] for x,y in native_route(case_suffix)]


def check():
    root=ET.fromstring(open_drive())
    road=root.find('road')
    if road is None or road.attrib['id']!='1':raise AssertionError('Authored road missing')
    elevations=road.findall('elevationProfile/elevation')
    if len(elevations)!=2 or float(elevations[1].attrib['a'])<=0:
        raise AssertionError('Hill crest missing')
    signal=road.find('signals/signal')
    if signal is None or signal.attrib['name']!='no_u_turn_prohibition_proposal' or float(signal.attrib['s'])>=80:
        raise AssertionError('Approach prohibition cue missing')
    lane_ids={int(row.attrib['id']) for row in road.findall('lanes/laneSection/*/lane')}
    if lane_ids!={-1,0,1}:raise AssertionError('Opposed lanes missing')
    results={}
    for suffix in ('witness_1','witness_2'):
        route=native_route(suffix)
        gaps=[math.dist(a,b) for a,b in zip(route,route[1:])]
        if max(gaps)>.11:raise AssertionError('Route discontinuity')
        if any(not -80<=x<=80 or not -8<=y<=8 for x,y in route):
            raise AssertionError('Native route leaves authored road')
        if route[0]!=[-50,4] or authored_route(suffix)!=[[x,-y] for x,y in route]:
            raise AssertionError('Native/OpenDRIVE reflection mismatch')
        if suffix=='witness_2' and (abs(route[-1][1]+4)>1e-9 or route[-1][0]>-40):
            raise AssertionError('Reversal does not enter opposing lane')
        results[suffix]={'route_points':len(route),'max_gap_m':max(gaps),
                         'start_native_xy_m':route[0],'end_native_xy_m':route[-1]}
    return {'passed':True,'scope':'authored map/route CPU only',
            'sign_official_native_verified':False,'hill_crest_native_verified':False,
            'physical_turn_verified':False,'cases':results}
