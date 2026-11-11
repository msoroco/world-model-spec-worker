import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('left_turn_capture_sources', ROOT/'capture_sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Box:
    def get_world_vertices(self, transform):
        x, y = transform.location.x, transform.location.y
        return [NS(x=x+dx,y=y+dy) for dx,dy in [(-2,-1),(2,-1),(2,1),(-2,1)]]


class Actor:
    def __init__(self, ident, x, lights):
        self.id, self.x, self.lights, self.bounding_box = ident,x,lights,Box()
    def get_transform(self):
        return NS(location=NS(x=self.x,y=0.0),rotation=NS(yaw=0.0))
    def get_velocity(self):
        return NS(x=3.0,y=0.0)
    def get_light_state(self):
        return self.lights


class CaptureSourcesTests(unittest.TestCase):
    def test_native_body_motion_and_indicator_readback(self):
        stream=io.StringIO()
        snap=NS(frame=42,timestamp=NS(elapsed_seconds=2.1))
        row=module.record_sample(stream,snapshot=snap,ego=Actor(12,1.0,4),
                                 oncoming=Actor(13,20.0,0),reciprocal=Actor(14,45.0,0),
                                 left_indicator_mask=4)
        self.assertEqual(json.loads(stream.getvalue()),row)
        self.assertEqual(row['ego']['body_vertices_xy_m'][0],[-1.0,-1.0])
        self.assertTrue(row['ego_left_indicator'])
        self.assertEqual(row['oncoming']['velocity_xy_mps'],[3.0,0.0])

    def test_duplicate_actor_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'identities repeat'):
            module.record_sample(io.StringIO(),snapshot=NS(frame=42,timestamp=NS(elapsed_seconds=2.1)),
                                 ego=Actor(12,1.0,4),oncoming=Actor(12,20.0,0),
                                 reciprocal=Actor(14,45.0,0),left_indicator_mask=4)

    def test_nonfinite_body_rejected(self):
        with self.assertRaisesRegex(ValueError,'Incomplete Native actor'):
            module.actor_sample(Actor(12,float('nan'),0))
