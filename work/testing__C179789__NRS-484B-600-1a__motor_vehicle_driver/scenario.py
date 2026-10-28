"""Paved two-lane road, fixed traffic participant, and speed-sweep route."""
import xml.etree.ElementTree as ET


def build_xodr():
    return '''<OpenDRIVE><header revMajor="1" revMinor="4" name="C179789-paved-traffic" version="1" date="2026-10-27" north="20" south="-20" east="500" west="0"/>
<road name="paved-straight" id="1" length="500" junction="-1"><link/><type s="0" type="rural"/>
<planView><geometry s="0" x="0" y="0" hdg="0" length="500"><line/></geometry></planView>
<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile><lateralProfile/>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width=".12"/></lane></center>
<right><lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" weight="standard" color="white" width=".12"/>
</lane><lane id="-2" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width=".12"/></lane></right></laneSection></lanes></road></OpenDRIVE>'''


def static_check():
    root = ET.fromstring(build_xodr())
    road = root.find('road')
    assert road.attrib['length'] == '500'
    assert len(road.findall('lanes/laneSection/right/lane')) == 2
    return {'paved_road_length_m': 500, 'same_direction_lanes': 2}


def route(role='ego'):
    y = -1.75 if role == 'ego' else -5.25
    start = 20 if role == 'ego' else 80
    return [(float(x), y) for x in range(start, 401)]
