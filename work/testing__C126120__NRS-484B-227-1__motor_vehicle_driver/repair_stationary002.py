"""Repair stationary divided-highway observations without changing the case plan."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work/_shared'))
from update002_tools import read,write,sha,update_case

TURN_SHAPE='''def turn_shape(p):
    import math
    rows = p['trajectory']
    if not rows:
        raise ValueError('Missing required source: case_observation.json:trajectory')
    if any(len(r['velocity_xy']) != 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in r['velocity_xy']) for r in rows):
        raise ValueError('Malformed source: case_observation.json:trajectory velocity_xy')
    centers = [[sum(v[j] for v in r['body_vertices_m']) / len(r['body_vertices_m']) for j in (0, 1)] for r in rows]
    moving = [r for r in rows if sum(v * v for v in r['velocity_xy']) > 0]
    observed = {'velocity_direction_available': bool(moving), 'moving_sample_count': len(moving),
                'original_body_center_path_xy_m': centers, 'original_velocity_xy': [r['velocity_xy'] for r in rows],
                'movement_count_is_not_a_legal_definition': True}
    if not moving:
        # A stationary capture is valid evidence of no observed translation.
        # There is no velocity direction to compare; do not invent an angle.
        observed['direction_observation'] = 'No nonzero velocity samples; turn direction is not observable from velocity.'
        return observed
    first, last = moving[0]['velocity_xy'], moving[-1]['velocity_xy']
    dot = sum(x * y for x, y in zip(first, last))
    cross = first[0] * last[1] - first[1] * last[0]
    observed['actual_velocity_direction_change_deg'] = math.degrees(math.atan2(cross, dot))
    return observed

'''

REGRESSION='''
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
'''

def repair_analysis(code):
    start=code.index('def turn_shape(p):');end=code.index('def statutory_observations(p):',start)
    code=code[:start]+TURN_SHAPE+code[end:]
    code=code.replace("    rows = p['trajectory']\n    first, last = (rows[0], rows[-1])", "    rows = p['trajectory']\n    if not rows:\n        raise ValueError('Missing required source: case_observation.json:trajectory')\n    first, last = (rows[0], rows[-1])")
    return code

def main():
    total=0
    for aid in ('testing__C126120__NRS-484B-227-1__motor_vehicle_driver','testing__C80909__NRS-484B-227-1__motor_vehicle_driver'):
        folder=ROOT/'work'/aid;manifest=read(folder/'execution-manifest.json')
        for entry in manifest['cases']:
            path=folder/entry['construction'];bundle=read(path);dest=path.parent
            analyzer=repair_analysis(next(f['content'] for f in bundle['files'] if f['path']=='analyze.py'))
            runner=next(f['content'] for f in bundle['files'] if f['path']=='runner.py')
            test_item=next(f for f in bundle['files'] if f['path']=='tests/test_case.py');test=test_item['content']
            if '# update002 stationary trajectory regression' not in test:test+=REGRESSION
            update_case(folder,entry,runner,analyzer)
            bundle=read(path);item=next(f for f in bundle['files'] if f['path']=='tests/test_case.py');item['content']=test;item['source']=str((dest/'tests/test_case.py').relative_to(ROOT))
            (dest/'tests/test_case.py').write_text(test);write(path,bundle)
            entry['construction_sha256']=sha(path);entry['measurement_procedure']['analysis_revision']=sha(dest/'analyze.py');total+=1
        write(folder/'execution-manifest.json',manifest)
    print('Repaired exact divided-highway analyzers and regression bundles:',total)
    assert total==8
if __name__=='__main__':main()
