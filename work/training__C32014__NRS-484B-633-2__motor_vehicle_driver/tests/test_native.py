import json
from pathlib import Path
import tempfile
import unittest
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey, validate_attempt_destination, TARGET_MPS
from finalize import finalize


class FakeCarla:
    class LaneType:
        Driving='driving'
    class Location:
        def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,z):
        self.road_id=1;self.lane_id=-1
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,z)})()


class FakeMap:
    def __init__(self,wrong_sign=False):self.wrong_sign=wrong_sign
    def to_opendrive(self):
        return open_drive().replace('value="25"','value="35"') if self.wrong_sign else open_drive()
    def get_waypoint(self,location,project_to_road,lane_type):
        z=8 if 0<=location.x<=100 else 0
        return FakeWaypoint(location.x,location.y,z)


class FakeWorld:
    def __init__(self,wrong_sign=False):self.mapping=FakeMap(wrong_sign)
    def get_map(self):return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry(self):
        g=geometry_check();self.assertEqual(g['posting_distance_m'],30.48)
        self.assertEqual(g['sign_limit_mph'],25)

    def test_capture_plan(self):
        p=runner_check();self.assertEqual(p['frames'],600)
        self.assertEqual(len(p['cameras']),4)
        self.assertFalse(p['physical_acceptance_claimed'])

    def test_exact_comparison_changes_speed_only(self):
        config=json.loads(Path('config.json').read_text())
        case=config['case_id'].rsplit('__',1)[-1]
        self.assertEqual(config['requested_speed_mps'],TARGET_MPS[case])
        self.assertEqual(config['supported_case_ids'],[
            config['case_id'].rsplit('__',1)[0]+'__probe_01',
            config['case_id'].rsplit('__',1)[0]+'__probe_02'])
        self.assertEqual(config['duration_s'],30)
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['cameras'][0]['name'],'overview')

    def test_materialized_destination_and_replay_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            self.assertEqual(validate_attempt_destination(folder),folder.resolve())
            (folder/'bridge-speed-history.jsonl').write_text('original')
            with self.assertRaisesRegex(ValueError,'already exists'):
                validate_attempt_destination(folder)

    def test_saved_finalizer_requires_original_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt=Path(tmp)/'attempt'
            attempt.mkdir()
            with self.assertRaisesRegex(ValueError,'Missing required source: bridge-speed-history.jsonl'):
                finalize(attempt,Path(tmp)/'report.json')

    def test_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)['bridge']),5)
        with self.assertRaisesRegex(RuntimeError,'sign readback differs'):
            survey(FakeWorld(wrong_sign=True),FakeCarla)
