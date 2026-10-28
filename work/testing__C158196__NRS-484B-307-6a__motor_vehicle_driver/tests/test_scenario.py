"""Static CPU check of exact authored route and native road metadata."""
import json
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import runner
import analyze

def test_authored_capability():
    runner.check()
    config=json.loads((ROOT/'config.json').read_text())
    assert config['case']['case_id'] in config['supported_case_ids']


class SourceMethodTests(unittest.TestCase):
    def test_signal_route_can_enter_intersection(self):
        for mode in ('signal_amber', 'signal_dark'):
            self.assertGreater(runner.route(1.75, mode)[-1][0], 7)

    def test_sign_join_and_phase_change(self):
        controls={'landmarks': [
            {'type':'274','road_id':2,'t_m':-5,'orientation':'+','s_m':45},
            {'type':'274','road_id':1,'t_m':-5,'orientation':'Orientation.Positive','s_m':45}]}
        self.assertEqual(len(analyze.approach_landmarks(controls,1,('274',))),1)
        states=[[{'id':9,'state':'TrafficLightState.Green','affected_road_ids':[1]}],
                [{'id':9,'state':'TrafficLightState.Yellow','affected_road_ids':[1]}]]
        self.assertEqual(analyze.phase_transition(states,1,'green','yellow'),(1,9))
        self.assertIsNone(analyze.phase_transition(states,2,'green','yellow'))
