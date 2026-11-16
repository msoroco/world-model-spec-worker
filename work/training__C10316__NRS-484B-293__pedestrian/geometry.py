"""Authored alley road and marked crosswalk proposal; Native load remains unproved."""
import json
import math
import xml.etree.ElementTree as ET

ROAD_ID=1
CROSSWALK_ID='C10316-authored-alley-crosswalk'
ROAD_LENGTH_M=40
ROAD_WIDTH_M=7
CROSSWALK_LENGTH_M=4
CROSSWALK_WIDTH_M=3


def open_drive():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',
                  name='C10316-alley-crosswalk-draft',version='1',
                  date='2026-11-06',north='25',south='-25',east='10',west='-10',
                  vendor='full-train-worker')
    road=ET.SubElement(root,'road',id=str(ROAD_ID),name='C10316_alley',
                       length=str(ROAD_LENGTH_M),junction='-1')
    ET.SubElement(road,'link')
    geometry=ET.SubElement(ET.SubElement(road,'planView'),'geometry',
                           s='0',x='0',y='-20',hdg=str(math.pi/2),
                           length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry,'line')
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',
                  s='0',a='0',b='0',c='0',d='0')
    lanes=ET.SubElement(road,'lanes')
    ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    left=ET.SubElement(section,'left')
    center=ET.SubElement(section,'center')
    ET.SubElement(center,'lane',id='0',type='none',level='false')
    right=ET.SubElement(section,'right')
    for parent,ident in ((left,1),(right,-1)):
        lane=ET.SubElement(parent,'lane',id=str(ident),type='driving',level='false')
        ET.SubElement(lane,'width',sOffset='0',a=str(ROAD_WIDTH_M/2),
                      b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='broken',
                      color='white',width='0.12')
    objects=ET.SubElement(road,'objects')
    ET.SubElement(objects,'object',id='1',name=CROSSWALK_ID,type='crosswalk',
                  s='20',t='0',zOffset='0',hdg='0',pitch='0',roll='0',
                  orientation='none',length=str(CROSSWALK_WIDTH_M),
                  width=str(CROSSWALK_LENGTH_M),height='0')
    ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def check():
    root=ET.fromstring(open_drive())
    road=root.find('road')
    assert road is not None and road.attrib['id']==str(ROAD_ID)
    assert road.find('planView/geometry/line') is not None
    assert len(road.findall('lanes/laneSection/left/lane'))==1
    assert len(road.findall('lanes/laneSection/right/lane'))==1
    obj=road.find('objects/object')
    assert obj is not None and obj.attrib['type']=='crosswalk'
    assert obj.attrib['name']==CROSSWALK_ID and float(obj.attrib['s'])==20
    assert float(obj.attrib['length'])==CROSSWALK_WIDTH_M
    assert float(obj.attrib['width'])==CROSSWALK_LENGTH_M
    assert ROAD_WIDTH_M>CROSSWALK_LENGTH_M
    # The two planned centers and 0.24 m footprints fit within the marked area.
    assert all(abs(y)+.12<CROSSWALK_WIDTH_M/2 for y in (-.65,.65))
    return {'road_id':ROAD_ID,'crosswalk_id':CROSSWALK_ID,
            'road_length_m':ROAD_LENGTH_M,'crosswalk_length_m':CROSSWALK_LENGTH_M,
            'crosswalk_width_m':CROSSWALK_WIDTH_M,
            'scope':'authored XML and analytic containment only; Native loading unverified'}


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True))
