import unittest,tempfile
from pathlib import Path
from runner import check
from analyze import finalize
class T(unittest.TestCase):
 def test_structure(self):self.assertTrue(check()['passed'])
 def test_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'Missing required source: case_observation.json'):finalize(Path(t),Path(t)/'analysis-report.json')

# update002 stationary trajectory regression
class StationaryTrajectoryTests(unittest.TestCase):
 def row(self,velocity):
  return {'frame':21714,'velocity_xy':velocity,'body_vertices_m':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]}
 def test_stationary_trajectory_has_no_invented_direction(self):
  from analyze import turn_shape
  observed=turn_shape({'trajectory':[self.row([0,0]),self.row([0,0])]})
  self.assertFalse(observed['velocity_direction_available'])
  self.assertEqual(observed['moving_sample_count'],0)
  self.assertNotIn('actual_velocity_direction_change_deg',observed)
  self.assertEqual(observed['original_velocity_xy'],[[0,0],[0,0]])
 def test_pauses_do_not_change_measured_direction(self):
  from analyze import turn_shape
  observed=turn_shape({'trajectory':[self.row(v) for v in ([0,0],[1,0],[0,0],[0,-1],[0,0])]})
  self.assertTrue(observed['velocity_direction_available'])
  self.assertEqual(observed['moving_sample_count'],2)
  self.assertEqual(observed['actual_velocity_direction_change_deg'],-90)
 def test_empty_trajectory_is_explicit_missing_evidence(self):
  from analyze import turn_shape,turn_trajectory
  for method in (turn_shape,turn_trajectory):
   with self.assertRaisesRegex(ValueError,'Missing required source: case_observation.json:trajectory'):
    method({'trajectory':[]})

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
