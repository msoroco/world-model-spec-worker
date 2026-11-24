"""Paved highway departure draft with travel lane and curbside shoulder."""
import json
import xml.etree.ElementTree as ET


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C227853-curb-departure',
                  version='1',date='2026-11-23',north='12',south='-12',east='80',west='-80',
                  vendor='full-train-worker')
    road=ET.SubElement(root,'road',id='1',name='curb-departure-road',length='160',junction='-1')
    ET.SubElement(road,'link')
    segment=ET.SubElement(ET.SubElement(road,'planView'),'geometry',
                          s='0',x='-80',y='0',hdg='0',length='160')
    ET.SubElement(segment,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',
                  s='0',a='0',b='0',c='0',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    ET.SubElement(section,'left')
    ET.SubElement(ET.SubElement(section,'center'),'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right')
    for lane_id,kind,width in ((-1,'driving',3.5),(-2,'shoulder',3.0)):
        lane=ET.SubElement(right,'lane',id=str(lane_id),type=kind,level='false')
        ET.SubElement(lane,'width',sOffset='0',a=str(width),b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='white',width='.1')
    ET.SubElement(road,'objects')
    ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def check():
    root=ET.fromstring(open_drive())
    road=root.find('road')
    lanes=road.findall('lanes/laneSection/right/lane')
    if [(int(x.attrib['id']),x.attrib['type']) for x in lanes]!=[
            (-1,'driving'),(-2,'shoulder')]:
        raise ValueError('curbside lane geometry changed')
    if float(road.attrib['length'])!=160:
        raise ValueError('road length changed')
    return {'passed':True,'road_id':1,'length_m':160,'driving_lane_id':-1,
            'curbside_shoulder_lane_id':-2,'curb_edge_source':'shoulder outer boundary',
            'physical_curb_verified':False,'Nevada_highway_dedication_verified':False,
            'parking_permission_verified':False}


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True))
