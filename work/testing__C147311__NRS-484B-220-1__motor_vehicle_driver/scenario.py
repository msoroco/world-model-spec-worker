"""One-way two-lane road and physical direction-sign capability construction."""
import xml.etree.ElementTree as ET


def build_xodr():
    # Both right lanes travel east. The opposite-direction case reverses the
    # actual vehicle heading/controller; it does not reclassify lane direction.
    return '''<OpenDRIVE><header revMajor="1" revMinor="4" name="C147311-one-way-two-lane" version="1" date="2026-10-27" north="20" south="-20" east="400" west="0"/>
<road name="one-way" id="1" length="400" junction="-1"><link/><type s="0" type="town"/>
<planView><geometry s="0" x="0" y="0" hdg="0" length="400"><line/></geometry></planView>
<elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width=".12"/></lane></center>
<right><lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" weight="standard" color="white" width=".12"/></lane>
<lane id="-2" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width=".12"/></lane></right></laneSection></lanes>
<signals><signal id="2201" name="OneWay" s="10" t="-7.4" zOffset="2" dynamic="no" orientation="+" country="US" type="R6-1" subtype="-1" value="-1" height=".8" width="1.4" text="ONE WAY" hOffset="0" pitch="0" roll="0"><validity fromLane="-2" toLane="-1"/></signal></signals>
</road></OpenDRIVE>'''


def static_check():
    root = ET.fromstring(build_xodr())
    road = root.find('road')
    assert road.attrib['length'] == '400'
    assert len(road.findall('lanes/laneSection/right/lane')) == 2
    assert not road.findall('lanes/laneSection/left/lane')
    sign = road.find('signals/signal')
    assert sign.attrib['name'] == 'OneWay' and sign.attrib['orientation'] == '+'
    return {'road_count': 1, 'eastbound_driving_lanes': 2, 'authored_direction_signs': 1}


def route(case):
    branch = case['variable_assignments']['test_branch']['value']
    if branch == 'designated_direction':
        return [(float(x), -1.75) for x in range(30, 261)]
    if branch == 'opposite_direction':
        return [(float(x), -1.75) for x in range(260, 29, -1)]
    raise ValueError('Unknown exact one-way branch')
