"""Authored roadway and fire-station driveway draft; identity remains unreviewed."""
import xml.etree.ElementTree as ET

ENTRANCE={'x_min_m':-3.0,'x_max_m':3.0,'road_edge_y_m':-4.0,'road_side':'south'}
FEET_20_M=6.096


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C229410 fire station entrance draft',version='1',date='2026-11-23',north='30',south='-30',east='80',west='-80',vendor='worker')
    road=ET.SubElement(root,'road',id='1',name='eastbound highway beside fire-station driveway',length='160',junction='-1')
    ET.SubElement(road,'link')
    geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-80',y='0',hdg='0',length='160')
    ET.SubElement(geometry,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(ET.SubElement(road,'lanes'),'laneSection',s='0')
    ET.SubElement(section,'left')
    center=ET.SubElement(section,'center'); ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right'); lane=ET.SubElement(right,'lane',id='-1',type='driving',level='false')
    ET.SubElement(lane,'width',sOffset='0',a='4',b='0',c='0',d='0')
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def check():
    root=ET.fromstring(open_drive())
    width=float(root.find('road/lanes/laneSection/right/lane/width').get('a'))
    if width!=4 or ENTRANCE['road_edge_y_m']!=-4 or FEET_20_M!=6.096:
        raise ValueError('Authored geometry or conversion differs')
    return {'passed':True,'road_width_m':width,'entrance':ENTRANCE,'twenty_feet_m':FEET_20_M,
            'official_station_identity_reviewed':False,'statutory_distance_method_adopted':False}
