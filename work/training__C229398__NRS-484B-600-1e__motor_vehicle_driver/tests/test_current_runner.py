"""CPU construction checks for exact approach-to-curb cases."""
import json
import unittest
from pathlib import Path

from road_geometry import check as check_road
from runner import check, control

ROOT=Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def test_exact_cases_and_road(self):
        self.assertEqual(check_road()['parking_lane'],-2)
        cfg=json.loads((ROOT/'config.json').read_text())
        self.assertIn(cfg['requested_approach_speed_mph'],(75.0,79.5,85.0))
        self.assertEqual(check(cfg)['frames'],600)

    def test_phase_controls_and_requested_not_measured(self):
        self.assertEqual(control(0,85,0,-300,-1.75)[0],'approach_driving')
        self.assertEqual(control(20,85,450,300,-1.75)[0],'curb_parking')
        self.assertEqual(control(0,85,550,600,-5)[0],'parked')
        self.assertEqual(control(0,85,0,-300,-1.75)[1],1.0)

    def test_wrong_cell_rejected(self):
        cfg=json.loads((ROOT/'config.json').read_text())
        cfg['frozen_cell']['maneuver']='travel'
        with self.assertRaisesRegex(ValueError,'Frozen cell'):
            check(cfg)
