import unittest
import hashlib
import json
import tempfile
from pathlib import Path

from geometry import check as geometry_check, open_drive
from runner import CAMERAS, check as runner_check, survey
from source_context import load_source_context


class FakeCarla:
    class LaneType:
        Driving='driving'
        Shoulder='shoulder'

    class Location:
        def __init__(self,x,y,z):
            self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,lane):
        self.road_id=1
        self.lane_id=lane
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,0)})()


class FakeMap:
    def __init__(self,wrong=False):
        self.wrong=wrong

    def get_waypoint(self,location,project_to_road,lane_type):
        lane=-1 if location.y>-3 else -2
        return FakeWaypoint(location.x,location.y,0 if self.wrong else lane)

    def to_opendrive(self):
        return open_drive()


class FakeWorld:
    def __init__(self,wrong=False):
        self.mapping=FakeMap(wrong)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_capture(self):
        self.assertEqual(geometry_check()['curbside_shoulder_lane_id'],-2)
        self.assertEqual(runner_check()['frames'],600)
        self.assertEqual(len(CAMERAS),4)

    def test_curb_and_travel_survey(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)['lanes']),2)
        with self.assertRaisesRegex(RuntimeError,'departure lane'):
            survey(FakeWorld(wrong=True),FakeCarla)

    def test_independent_authority_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            sources = {}
            for fact in ('highway_dedication','public_access','curb_permission','parking_purpose'):
                path = folder / (fact + '.txt')
                path.write_text('Synthetic CPU test source for ' + fact + '\n')
                sources[fact] = {'path': path.name, 'sha256': hashlib.sha256(
                    path.read_bytes()).hexdigest(), 'citation': 'synthetic CPU fixture'}
            manifest = {'format':'c227853-authority-context-v1','state':'Nevada',
                        'public_highway':True,'parking_permitted':True,
                        'initial_status':'parked_no_loading','sources':sources}
            path = folder / 'context.json'
            path.write_text(json.dumps(manifest))
            accepted = load_source_context(path)
            self.assertEqual(accepted['curb_permission_source_sha256'],
                             sources['curb_permission']['sha256'])
            for mutate in ('no_citation','wrong_hash','missing_file','no_permission'):
                broken = json.loads(json.dumps(manifest))
                if mutate == 'no_citation':
                    broken['sources']['public_access']['citation'] = ''
                elif mutate == 'wrong_hash':
                    broken['sources']['parking_purpose']['sha256'] = '0' * 64
                elif mutate == 'missing_file':
                    broken['sources']['highway_dedication']['path'] = 'gone.txt'
                else:
                    broken['parking_permitted'] = None
                path.write_text(json.dumps(broken))
                with self.assertRaises(ValueError, msg=mutate):
                    load_source_context(path)
