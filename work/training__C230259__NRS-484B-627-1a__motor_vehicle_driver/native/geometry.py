"""Two-way one-lane-per-direction road with measured paved right margin."""
import json
import xml.etree.ElementTree as ET


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C230259-extreme-right',
                  version='1',date='2026-11-23',north='12',south='-12',east='80',west='-80',
                  vendor='full-train-worker')
    road=ET.SubElement(root,'road',id='1',name='two-way-paved-highway-draft',length='160',junction='-1')
    ET.SubElement(road,'link')
    segment=ET.SubElement(ET.SubElement(road,'planView'),'geometry',
                          s='0',x='-80',y='0',hdg='0',length='160')
    ET.SubElement(segment,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    left=ET.SubElement(section,'left')
    lane=ET.SubElement(left,'lane',id='1',type='driving',level='false')
    ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
    ET.SubElement(lane,'roadMark',sOffset='0',type='solid',color='white',width='.1')
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
    left=road.findall('lanes/laneSection/left/lane')
    right=road.findall('lanes/laneSection/right/lane')
    if [(int(x.attrib['id']),x.attrib['type']) for x in left+right]!=[
            (1,'driving'),(-1,'driving'),(-2,'shoulder')]:
        raise ValueError('one driving lane each direction and paved margin required')
    if [float(x.find('width').attrib['a']) for x in left+right]!=[3.5,3.5,3.0]:
        raise ValueError('paved widths changed')
    return {'passed':True,'road_id':1,'length_m':160,'forward_lane_id':-1,
            'opposing_lane_id':1,'right_shoulder_lane_id':-2,
            'forward_lane_width_m':3.5,'right_paved_margin_width_m':3.0,
            'right_paved_edge_y_m':-6.5,'highway_public_status_verified':False,
            'physical_width_and_edge_verified':False}


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True))
