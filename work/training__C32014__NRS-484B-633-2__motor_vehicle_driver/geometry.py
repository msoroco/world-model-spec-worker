"""Authored elevated structure with 100-foot approach postings."""
import json
import xml.etree.ElementTree as ET

FEET_100_M = 30.48
LIMIT_MPH = 25.0
BRIDGE_X_M = [0.0, 100.0]


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C32014-bridge-maximum',
                  version='1',date='2026-11-23',north='20',south='-20',east='200',west='-100',
                  vendor='full-train-worker')
    road=ET.SubElement(root,'road',id='1',name='elevated-bridge-highway',length='300',junction='-1')
    ET.SubElement(road,'link')
    geom=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-100',y='0',hdg='0',length='300')
    ET.SubElement(geom,'line')
    profile=ET.SubElement(road,'elevationProfile')
    for s,a,b in ((0,0,0),(50,0,.16),(100,8,0),(200,8,-.16),(250,0,0)):
        ET.SubElement(profile,'elevation',s=str(s),a=str(a),b=str(b),c='0',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    left=ET.SubElement(section,'left');center=ET.SubElement(section,'center');right=ET.SubElement(section,'right')
    ET.SubElement(center,'lane',id='0',type='none',level='false')
    for parent,lane_id in ((left,1),(right,-1)):
        lane=ET.SubElement(parent,'lane',id=str(lane_id),type='driving',level='false')
        ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='white',width='.12')
    ET.SubElement(road,'objects')
    signals=ET.SubElement(road,'signals')
    for sid,s,t,orientation in (('101',100-FEET_100_M,-5,'+'),('102',200+FEET_100_M,5,'-')):
        ET.SubElement(signals,'signal',id=sid,s=f'{s:.2f}',t=str(t),
                      name='BRIDGE STRUCTURE MAXIMUM 25 MPH',dynamic='no',
                      orientation=orientation,zOffset='2',country='USA',
                      type='bridge_structure_maximum',subtype='speed',value='25',unit='mph',
                      hOffset='0',pitch='0',roll='0')
    return ET.tostring(root,encoding='unicode')


def check():
    root=ET.fromstring(open_drive());road=root.find('road')
    signals=road.findall('signals/signal')
    if road.attrib['length']!='300' or len(signals)!=2:
        raise ValueError('bridge/sign inventory changed')
    if abs((100-float(signals[0].attrib['s']))-FEET_100_M)>1e-6:
        raise ValueError('near approach posting distance changed')
    if abs((float(signals[1].attrib['s'])-200)-FEET_100_M)>1e-6:
        raise ValueError('far approach posting distance changed')
    if [s.attrib['orientation'] for s in signals]!=['+','-']:
        raise ValueError('approach sign directions changed')
    if [s.attrib['value'] for s in signals]!=['25','25']:
        raise ValueError('structural maximum sign values changed')
    return {'passed':True,'bridge_x_m':BRIDGE_X_M,'deck_z_m':8,
            'posting_distance_m':FEET_100_M,'sign_limit_mph':LIMIT_MPH,
            'native_bridge_mesh_verified':False,'department_determination_verified':False}


if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
