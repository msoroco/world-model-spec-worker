import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_samples import sample


def actor(identity, x):
    vertices = [S(x=x+dx,y=y,z=0) for dx,y in
                [(-.2,-.2),(-.2,.2),(.2,-.2),(.2,.2)]]
    return S(id=identity, get_transform=lambda: None,
             bounding_box=S(get_world_vertices=lambda transform: vertices))


class NativeSampleTests(unittest.TestCase):
    def test_original_three_actor_body_identity(self):
        actors = {'sign': actor(1,-8), 'bicycle': actor(2,-5),
                  'operator': actor(3,-5)}
        row = sample(actors,frame=200,time_s=10.,phase='dismount_hold')
        self.assertEqual((row['frame'],row['sign_id'],row['bicycle_id'],row['operator_id']),
                         (200,1,2,3))
        self.assertEqual(len(row['operator_body_vertices_m']),4)
        actors['operator'] = actor(2,-5)
        with self.assertRaisesRegex(ValueError,'distinct Native actors'):
            sample(actors,frame=201,time_s=10.05,phase='afoot_reversal')

    def test_invalid_phase_and_nonfinite_body_rejected(self):
        actors = {'sign': actor(1,-8), 'bicycle': actor(2,-5),
                  'operator': actor(3,-5)}
        with self.assertRaisesRegex(ValueError,'unknown constructed turn phase'):
            sample(actors,frame=200,time_s=10.,phase='legal_dismount')
        actors['operator'] = actor(3,float('nan'))
        with self.assertRaisesRegex(ValueError,'body geometry missing'):
            sample(actors,frame=200,time_s=10.,phase='afoot_reversal')
