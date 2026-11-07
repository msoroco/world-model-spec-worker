"""CPU checks for the authored center-lane type and proposed Native readback."""
import enum
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from geometry import open_drive
from runner import map_survey


class LaneType(enum.IntFlag):
    Driving = 1
    Bidirectional = 2


def waypoint(road_id, lane_id, lane_type, y, forward):
    vector=SimpleNamespace(x=forward[0],y=forward[1])
    transform=SimpleNamespace(location=SimpleNamespace(y=y),
                              get_forward_vector=lambda:vector)
    return SimpleNamespace(road_id=road_id,lane_id=lane_id,lane_type=lane_type,
                           lane_width=3.5,transform=transform)


class Mapping:
    def __init__(self,center_type):
        self.center_type=center_type

    def get_waypoint(self,location,*,project_to_road,lane_type):
        if location.y==0:
            return waypoint(1,-1,self.center_type,0,[1,0])
        if location.y==3.5:
            return waypoint(1,-2,LaneType.Driving,3.5,[1,0])
        return waypoint(4,-1,LaneType.Driving,-30,[0,-1])


class LaneDesignTests(unittest.TestCase):
    def test_source_has_one_bidirectional_turn_lane(self):
        root=ET.fromstring(open_drive())
        found=[(road.attrib['id'],lane) for road in root.findall('road')
               for lane in road.findall("./lanes/laneSection/right/lane[@type='bidirectional']")]
        self.assertEqual([(road,lane.attrib['id']) for road,lane in found],[('1','-1')])
        self.assertEqual(found[0][1].find("userData[@code='lane_use']").attrib['value'],
                         'left_turn_only_both_directions')

    def test_native_type_readback_is_separate_from_design_approval(self):
        carla=SimpleNamespace(LaneType=LaneType,
                              Location=lambda **values:SimpleNamespace(**values))
        survey=map_survey(carla,Mapping(LaneType.Bidirectional),'a'*64)
        self.assertTrue(survey['native_center_lane_bidirectional_type_verified'])
        self.assertFalse(survey['native_center_lane_design_verified'])

    def test_native_readback_rejects_driving_lane(self):
        carla=SimpleNamespace(LaneType=LaneType,
                              Location=lambda **values:SimpleNamespace(**values))
        with self.assertRaisesRegex(RuntimeError,'Native lane type differs'):
            map_survey(carla,Mapping(LaneType.Driving),'a'*64)


if __name__=='__main__':unittest.main()
