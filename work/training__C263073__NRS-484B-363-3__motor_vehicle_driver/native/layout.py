"""Authored two-way school-adjacent road and turn envelope; designation unreviewed."""
import math
import xml.etree.ElementTree as ET

ZONE={'x_min_m':-20,'x_max_m':20,'y_min_m':-8,'y_max_m':8}
TURN={'center_x_m':-12,'center_y_m':0,'radius_m':3,'first_frame':100,'last_frame':180}


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C263073 school zone draft',version='1',date='2026-11-23',north='30',south='-30',east='60',west='-60',vendor='worker')
    road=ET.SubElement(root,'road',id='1',name='school-adjacent two-way road',length='120',junction='-1')
    ET.SubElement(road,'link');geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-60',y='0',hdg='0',length='120')
    ET.SubElement(geometry,'line');ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(ET.SubElement(road,'lanes'),'laneSection',s='0')
    left=ET.SubElement(section,'left');plus=ET.SubElement(left,'lane',id='1',type='driving',level='false')
    ET.SubElement(plus,'width',sOffset='0',a='6',b='0',c='0',d='0')
    center=ET.SubElement(section,'center');ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right');minus=ET.SubElement(right,'lane',id='-1',type='driving',level='false')
    ET.SubElement(minus,'width',sOffset='0',a='6',b='0',c='0',d='0')
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def planned_pose(index,turn):
    if not turn:
        return (-25+min(index,250)*.2,-3,0)
    if index<100:return (-25+index*.13,-3,0)
    if index<=180:
        angle=-math.pi/2+math.pi*(index-100)/80
        return (TURN['center_x_m']+3*math.cos(angle),3*math.sin(angle),
            90+math.degrees(angle))
    return (-12-min(index-180,160)*.2,3,180)


def check():
    root=ET.fromstring(open_drive());lanes=root.findall('road/lanes/laneSection/left/lane')+root.findall('road/lanes/laneSection/right/lane')
    if [x.get('id') for x in lanes]!=['1','-1']:raise ValueError('Two-way turning envelope missing')
    a=planned_pose(100,True);b=planned_pose(180,True)
    if abs(a[1]+3)>1e-6 or abs(b[1]-3)>1e-6 or abs(b[2]-180)>1e-6:
        raise ValueError('Authored reversal differs')
    return {'passed':True,'zone':ZONE,'turn':TURN,'road_lane_ids':[1,-1],
        'zone_designation_reviewed':False,'child_age_or_presence_rule_adopted':False}
