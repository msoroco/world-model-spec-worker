"""Straight marked-road/shoulder proposal for original CARLA map readback."""

import math
import xml.etree.ElementTree as ET


ROAD_LENGTH_M = 180.0
TRAVEL_LANE_Y_M = (0.0, 4.0)
PAVED_SHOULDER_Y_M = (4.0, 6.0)
EGO_HALF_WIDTH_M = 0.9


def open_drive():
    return '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="c179776-marked-road" version="1.00" date="2026-11-27" north="6" south="-4" east="180" west="0" vendor="worker"/>
  <road name="surveyed controlled-access candidate" length="180" id="1" junction="-1">
    <type s="0" type="motorway"><speed max="60" unit="mph"/></type>
    <planView><geometry s="0" x="0" y="0" hdg="0" length="180"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneSection s="0">
      <left>
        <lane id="2" type="shoulder" level="false"><width sOffset="0" a="2" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.15"/></lane>
        <lane id="1" type="driving" level="false"><width sOffset="0" a="4" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.15"/></lane>
      </left>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.15"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><width sOffset="0" a="4" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.15"/></lane></right>
    </laneSection></lanes>
  </road>
</OpenDRIVE>'''


def planned_xy(case, elapsed_s):
    """Controller target; its requested path never substitutes for motion evidence."""
    if case not in ('marked_lane', 'paved_shoulder'):
        raise ValueError('Unknown exact lane target')
    if not 0 <= elapsed_s < 30:
        raise ValueError('Outside recorded episode')
    # OpenDRIVE positive lane IDs travel opposite increasing road station.
    x = 132.0 - 4.0 * elapsed_s
    if case == 'marked_lane':
        y = 2.5
    else:
        u = min(1.0, max(0.0, (elapsed_s - 10.0) / 4.0))
        y = 2.5 + 2.5 * (3 * u * u - 2 * u * u * u)
    return x, y


def inspect(case, source_xml=None):
    root = ET.fromstring(open_drive() if source_xml is None else source_xml)
    road = root.find('road')
    if road is None or float(road.attrib['length']) != ROAD_LENGTH_M:
        raise ValueError('Authored road extent differs')
    lanes = {int(lane.attrib['id']): lane for lane in root.findall('.//laneSection/*/lane')}
    if (lanes[1].attrib['type'], lanes[2].attrib['type'], lanes[-1].attrib['type']) != ('driving', 'shoulder', 'driving'):
        raise ValueError('Road lane types differ')
    if any(float(lanes[lane].find('width').attrib['a']) != width for lane, width in ((1, 4), (2, 2), (-1, 4))):
        raise ValueError('Road lane widths differ')
    points = [planned_xy(case, i / 20) for i in range(600)]
    if not all(points[i + 1][0] < points[i][0] for i in range(599)):
        raise ValueError('Positive-ID lane travel direction differs')
    if any(not math.isfinite(x) or not math.isfinite(y) or x < 0 or x > ROAD_LENGTH_M or y - EGO_HALF_WIDTH_M < 0 or y + EGO_HALF_WIDTH_M > 6 for x, y in points):
        raise ValueError('Target body leaves authored corridor')
    fully_shoulder = sum(y - EGO_HALF_WIDTH_M >= PAVED_SHOULDER_Y_M[0] and y + EGO_HALF_WIDTH_M <= PAVED_SHOULDER_Y_M[1] for _, y in points)
    outside = sum(y + EGO_HALF_WIDTH_M > TRAVEL_LANE_Y_M[1] for _, y in points)
    if case == 'marked_lane' and (outside or fully_shoulder):
        raise ValueError('Marked-lane target leaves lane')
    if case == 'paved_shoulder' and (outside < 300 or fully_shoulder < 250):
        raise ValueError('Paved-shoulder target lacks excursion')
    return {'case': case, 'frames': len(points), 'rate_hz': 20,
            'outside_target_frames': outside, 'fully_shoulder_target_frames': fully_shoulder,
            'native_map_readback_complete': False, 'physical_motion_verified': False,
            'controlled_access_designation_verified': False}
