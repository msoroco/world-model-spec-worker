"""Exercise the selected fallback Native site source on fake CARLA geometry."""
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_native_site import FakeWorld, NativeSiteTests, transform


class FallbackSpawnTests(unittest.TestCase):
    def test_fallback_uses_second_verified_waypoint(self):
        for suffix in ('below', 'equal', 'above'):
            with self.subTest(suffix=suffix):
                bundle = json.loads((ROOT / f'fallback1-construction-{suffix}.json').read_text())
                source = next(item['content'] for item in bundle['files']
                              if item['path'] == 'native_site.py')
                module = types.ModuleType(f'fallback_site_{suffix}')
                exec(compile(source, f'fallback_site_{suffix}.py', 'exec'), module.__dict__)
                fixture = NativeSiteTests('test_constructs_exact_actor_and_four_cameras_with_source_hash')
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                case_id = ROOT.name + '__' + suffix
                fixture.packet['case_id'] = case_id
                fixture.save()
                world = FakeWorld()
                points = []
                original_spawn = world.spawn_actor

                def record_spawn(blueprint, pose, attach_to=None):
                    if attach_to is None:
                        points.append(pose.location.x)
                    return original_spawn(blueprint, pose, attach_to=attach_to)

                world.spawn_actor = record_spawn
                site = module.construct(world, fixture.path, case_id, transform)
                self.assertEqual(points, [10])
                self.assertEqual(len(site.cameras), 4)
                site.close()


if __name__ == '__main__':
    unittest.main()
