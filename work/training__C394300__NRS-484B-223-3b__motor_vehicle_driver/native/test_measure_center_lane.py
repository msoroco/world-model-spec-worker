"""Adversarial CPU checks for source-bound center-lane distance intervals."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from measure_center_lane import THRESHOLD_M,measure


def fixture(root,distance_m):
    geometry={'center_turn_lane_native_xy_bounds_m':[-70,-1.75,0,1.75],
              'center_turn_lane_native_id':-1,
              'approach_forward_native_xy':[1,0],
              'native_center_lane_design_verified':False}
    (root/'road_geometry.json').write_text(json.dumps(geometry))
    xs=[-74,-72,-67]
    destination=-72+distance_m
    while xs[-1]+.25<destination-.25:xs.append(xs[-1]+.25)
    if xs[-1]>=destination-.25:xs.pop()
    xs.extend([destination-.25,destination])
    rows=[]
    for i,x in enumerate(xs):
        angle=math.radians(6) if i==len(xs)-1 else 0
        fx,fy=math.cos(angle),math.sin(angle);rx,ry=-fy,fx
        body=[[x+d*2.5*fx+s*1.0*rx,d*2.5*fy+s*1.0*ry]
              for d,s in ((-1,-1),(-1,1),(1,1),(1,-1))]
        rows.append({'native_frame':100+i,'time_s':.05*(i+1),
                     'native_center_xy_m':[x,0],'native_body_xy_m':body,
                     'native_forward_xy':[fx,fy],
                     'native_lane_id':-2 if i<2 else -1})
    (root/'native_samples.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    return rows


class CenterLaneMeasurement(unittest.TestCase):
    def evaluate(self,feet):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);fixture(root,feet*.3048)
            return measure(root/'native_samples.jsonl',root/'road_geometry.json')

    def test_clear_within(self):
        report=self.evaluate(180)
        self.assertEqual(report['threshold_relation'],'within_200_feet')
        self.assertFalse(report['native_center_lane_design_verified'])

    def test_clear_excess(self):
        self.assertEqual(self.evaluate(220)['threshold_relation'],'exceeds_200_feet')

    def test_exact_boundary_unresolved(self):
        report=self.evaluate(200)
        self.assertEqual(report['threshold_relation'],'unresolved_at_200_feet')
        self.assertLessEqual(report['entry_to_turn_distance_interval_m'][0],THRESHOLD_M)
        self.assertGreaterEqual(report['entry_to_turn_distance_interval_m'][1],THRESHOLD_M)

    def test_one_foot_probes_preserve_sampling_uncertainty(self):
        self.assertEqual(self.evaluate(199)['threshold_relation'],'unresolved_at_200_feet')
        self.assertEqual(self.evaluate(201)['threshold_relation'],'exceeds_200_feet')

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);fixture(root,180*.3048)
            (root/'native_samples.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure(root/'native_samples.jsonl',root/'road_geometry.json')

    def test_lane_switch_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);rows=fixture(root,180*.3048)
            rows[len(rows)//2]['native_lane_id']=-2
            (root/'native_samples.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'Continuous sampled center-lane occupancy absent'):
                measure(root/'native_samples.jsonl',root/'road_geometry.json')

    def test_missing_turn_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);rows=fixture(root,180*.3048)
            rows[-1]['native_forward_xy']=[1,0]
            (root/'native_samples.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'Observed left-turn onset absent'):
                measure(root/'native_samples.jsonl',root/'road_geometry.json')


if __name__=='__main__':unittest.main()
