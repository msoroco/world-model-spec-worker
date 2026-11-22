import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wheelchair_runner',ROOT/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def body(x,y):return [[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]
def wheelchair(y):
    person={'role':'person_in_manual_wheelchair','source_ref':'original/person-body',
            'body_vertices_m':body(0,y)}
    chair={'kind':'manual_wheelchair','source_ref':'original/chair-body',
           'body_vertices_m':body(0,y)}
    return person,chair


class WheelchairControllerTests(unittest.TestCase):
    def setUp(self):self.scene=runner.load_scene()
    def test_crossing_path_and_braking_response(self):
        person,chair=wheelchair(0)
        approaching=runner.encounter(self.scene,body(-5,0),person,chair,2,1)
        self.assertEqual(approaching['time_to_path_s'],2)
        self.assertEqual(runner.control(self.scene,approaching)['brake'],1.0)
        distant=runner.encounter(self.scene,body(-20,0),person,chair,2,1)
        self.assertEqual(runner.control(self.scene,distant)['brake'],0.0)
        self.assertIsNone(runner.control(self.scene,approaching)['legal_due_care_verdict'])
    def test_clear_and_collision_geometry(self):
        person,chair=wheelchair(8)
        clear=runner.encounter(self.scene,body(-5,0),person,chair,2,0)
        self.assertFalse(clear['pedestrian_in_or_approaching_lane'])
        self.assertEqual(runner.control(self.scene,clear)['brake'],0.0)
        person,chair=wheelchair(0)
        contact=runner.encounter(self.scene,body(0,0),person,chair,2,1)
        self.assertTrue(contact['collision_observed'])
    def test_requires_person_chair_association_and_sources(self):
        person,chair=wheelchair(0)
        chair['body_vertices_m']=body(20,20)
        with self.assertRaises(ValueError):
            runner.encounter(self.scene,body(-5,0),person,chair,2,1)
        person,chair=wheelchair(0);person.pop('source_ref')
        with self.assertRaises(ValueError):
            runner.encounter(self.scene,body(-5,0),person,chair,2,1)
        person,chair=wheelchair(0)
        with self.assertRaises(ValueError):
            runner.encounter(self.scene,body(-5,0),person,chair,-1,1)


if __name__=='__main__':unittest.main()
