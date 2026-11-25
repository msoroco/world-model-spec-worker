"""Wide highway approach with a backing path; physical precedence remains unresolved."""
import xml.etree.ElementTree as ET

CONFLICT={'x_min_m':8,'x_max_m':16,'y_min_m':-5,'y_max_m':-1}


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C230259 backing highway draft',version='1',date='2026-11-23',north='20',south='-20',east='80',west='-80',vendor='worker')
    road=ET.SubElement(root,'road',id='1',name='eastbound highway with backing approach',length='160',junction='-1')
    ET.SubElement(road,'link')
    geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-80',y='0',hdg='0',length='160')
    ET.SubElement(geometry,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(ET.SubElement(road,'lanes'),'laneSection',s='0')
    ET.SubElement(section,'left');center=ET.SubElement(section,'center')
    ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right');lane=ET.SubElement(right,'lane',id='-1',type='driving',level='false')
    ET.SubElement(lane,'width',sOffset='0',a='9',b='0',c='0',d='0')
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def check():
    width=float(ET.fromstring(open_drive()).find('road/lanes/laneSection/right/lane/width').get('a'))
    if width!=9 or CONFLICT['y_max_m']!=-1:raise ValueError('Authored highway geometry differs')
    return {'passed':True,'road_width_m':width,'conflict_region':CONFLICT,
            'section_stem_recovered':True,'right_of_way_determined':False}
