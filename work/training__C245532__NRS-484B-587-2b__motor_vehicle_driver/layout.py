"""Same-direction traffic and entrance lanes with authored solid white separator."""
import xml.etree.ElementTree as ET

SEPARATOR={'y_m':-3.5,'x_min_m':-60,'x_max_m':60,'form':'solid','color':'white',
    'inner_lane_id':-1,'outer_lane_id':-2}


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C245532 controlled-access lane draft',version='1',date='2026-11-23',north='20',south='-20',east='60',west='-60',vendor='worker')
    road=ET.SubElement(root,'road',id='1',name='eastbound controlled-access highway draft',length='120',junction='-1')
    ET.SubElement(road,'link');ET.SubElement(ET.SubElement(road,'type',s='0',type='motorway'),'speed',max='55',unit='mph')
    geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-60',y='0',hdg='0',length='120')
    ET.SubElement(geometry,'line');ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(ET.SubElement(road,'lanes'),'laneSection',s='0');ET.SubElement(section,'left')
    center=ET.SubElement(section,'center');ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right')
    for lane_id,name in ((-1,'marked traffic lane'),(-2,'entrance lane')):
        lane=ET.SubElement(right,'lane',id=str(lane_id),type='driving',level='false')
        ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='white',width='0.15')
        ET.SubElement(lane,'userData',code='lane_function',value=name)
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def check():
    root=ET.fromstring(open_drive());lanes=root.findall('road/lanes/laneSection/right/lane')
    if len(lanes)!=2 or [x.get('id') for x in lanes]!=['-1','-2']:
        raise ValueError('Two same-direction lanes missing')
    marks=[x.find('roadMark') for x in lanes]
    if any(x.get('type')!='solid' or x.get('color')!='white' for x in marks):
        raise ValueError('Separator form/color differs')
    return {'passed':True,'lane_ids':[-1,-2],'separator':SEPARATOR,
        'public_highway_and_access_authority_reviewed':False,'official_entrance_function_reviewed':False}
