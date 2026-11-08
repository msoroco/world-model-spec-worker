"""Pedestrian-specific OpenDRIVE sidewalk and obstruction placement proposal.

This extends the existing alley cell without changing its driving or bicycle
lanes. Native map readback and physical prop clearance remain to be captured.
"""
import json
import xml.etree.ElementTree as ET

from alley_geometry import open_drive as alley_open_drive
from pedestrian_engineering import (
    SIDEWALK_PASSAGE_BOUNDS_M, BUFFER_PASSAGE_BOUNDS_M,
    pedestrian_pose, FRAMES,
)
from measure_facility import overlap_area

SIDEWALK_LANE_ID = -3
SIDEWALK_WIDTH_M = 2.5
SIDEWALK_LANE_CENTER_Y_M = -6.25


def open_drive():
    root = ET.fromstring(alley_open_drive())
    right = root.find("road[@id='1']/lanes/laneSection/right")
    if right is None or right.find("lane[@id='-3']") is not None:
        raise ValueError('Expected original right-side bicycle lane only')
    sidewalk = ET.SubElement(right, 'lane', id=str(SIDEWALK_LANE_ID),
                             type='sidewalk', level='false')
    ET.SubElement(sidewalk, 'width', sOffset='0', a=str(SIDEWALK_WIDTH_M),
                  b='0', c='0', d='0')
    ET.SubElement(sidewalk, 'roadMark', sOffset='0', type='solid',
                  color='white', width='0.12')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    right = root.find("road[@id='1']/lanes/laneSection/right")
    lanes = [(int(lane.get('id')), lane.get('type'),
              float(lane.find('width').get('a'))) for lane in right.findall('lane')]
    if lanes != [(-1, 'driving', 3.0), (-2, 'biking', 2.0),
                 (-3, 'sidewalk', SIDEWALK_WIDTH_M)]:
        raise ValueError('Pedestrian road lane geometry changed')
    path = [pedestrian_pose(i) for i in range(FRAMES)]
    if path[0]['center_xy'][1] != -7.0 or path[160]['center_xy'][1] != -4.0:
        raise ValueError('Pedestrian proposal misses sidewalk/lane sequence')
    if path[260]['center_xy'][1] != -7.0:
        raise ValueError('Pedestrian return is missing')
    if overlap_area(path[200]['body_xy'], (-2.5,-5.0,2.5,-3.0)) <= .01:
        raise ValueError('Pedestrian does not traverse conflict region')
    return {'road_id': 1, 'sidewalk_lane_id': SIDEWALK_LANE_ID,
            'sidewalk_width_m': SIDEWALK_WIDTH_M,
            'sidewalk_lane_center_y_m': SIDEWALK_LANE_CENTER_Y_M,
            'sidewalk_passage_bounds_m': list(SIDEWALK_PASSAGE_BOUNDS_M),
            'buffer_passage_bounds_m': list(BUFFER_PASSAGE_BOUNDS_M),
            'frames': FRAMES, 'native_map_readback_verified': False,
            'physical_obstruction_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
