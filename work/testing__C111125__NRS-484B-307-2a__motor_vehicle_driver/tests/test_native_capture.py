import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from test_native_scene import ref, site


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class World:
    frame = 0
    gap_at = None

    def tick(self):
        self.frame += 1
        return self.frame + (1 if self.frame == self.gap_at else 0)

    def get_snapshot(self):
        timestamp = type('Timestamp', (), {'elapsed_seconds': self.frame * .05})()
        return type('Snapshot', (), {'frame': self.frame, 'timestamp': timestamp})()


class Ego:
    id = 11

    def __init__(self, world):
        self.world = world
        self.braked = False

    def get_location(self):
        return Vector(x=-4 + 8 * (self.world.frame - 1) / 899)

    def get_velocity(self):
        return Vector(x=2)

    def set_target_velocity(self, value):
        self.braked = value.x == value.y == value.z == 0


class Other:
    id = 12

    def get_location(self):
        return Vector(x=0, y=0)


def green(_snapshot, _head):
    return {'head_id': 'head-7', 'facing_approach_id': 'north',
            'lit_aspects': ['circular_green']}


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111125-2a-tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = site(self.root)
        self.site_ref = ref(self.root, 'site.json', self.site)

    def test_clear_green_original_900_frames(self):
        world = World()
        ego = Ego(world)
        result = capture(world, ego, None, self.site, self.site_ref,
                         'green_clear', green, self.root,
                         camera_profile_sha256='source-hashed-profile')
        self.assertEqual(result['measurement']['frame_count'], 900)
        self.assertEqual(result['receipt']['frame_count'], 900)
        self.assertFalse(result['receipt']['camera_capture_complete'])
        self.assertIsNone(result['measurement']['right_of_way_verdict'])
        self.assertTrue(ego.braked)

    def test_vehicle_context_is_hash_bound(self):
        world = World()
        ego = Ego(world)
        context = ref(self.root, 'reviewed-traffic-context.json',
                      {'kind': 'diagnostic', 'lawful_presence': 'unresolved'})
        result = capture(world, ego, Other(), self.site, self.site_ref,
                         'green_vehicle_present', green, self.root, context,
                         camera_profile_sha256='source-hashed-profile')
        user = result['measurement']['exhibition']['other_users'][0]
        self.assertEqual(user['region'], 'intersection')
        self.assertEqual(user['lawful_presence_source'], context['path'])

    def test_frame_and_signal_failure_leave_no_receipt(self):
        world = World()
        world.gap_at = 40
        ego = Ego(world)
        with self.assertRaisesRegex(ValueError, 'tick and snapshot'):
            capture(world, ego, None, self.site, self.site_ref,
                    'green_clear', green, self.root,
                    camera_profile_sha256='source-hashed-profile')
        self.assertFalse((self.root / 'original-events.json').exists())
        self.assertFalse((self.root / 'original-capture-receipt.json').exists())
        self.assertTrue(ego.braked)
        world = World()
        ego = Ego(world)
        def mixed(snapshot, head):
            value = green(snapshot, head)
            if snapshot.frame == 100:
                value['lit_aspects'] = ['circular_green', 'green_arrow']
            return value
        with self.assertRaisesRegex(ValueError, 'not evidenced throughout'):
            capture(world, ego, None, self.site, self.site_ref,
                    'green_clear', mixed, self.root,
                    camera_profile_sha256='source-hashed-profile')
        self.assertTrue((self.root / 'original-events.json').exists())
        self.assertFalse((self.root / 'original-capture-receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
