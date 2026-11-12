import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('physical_audit', ROOT / 'opposing_turn_physical_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(frame, x, y, inside, actor):
    return {'frame': frame, 'time_s': frame * .05, 'center_xy': [x, y],
            'heading_xy': [1, 0], 'ground_corners_xy': [[x-.2,y-.2],[x+.2,y-.2],
            [x+.2,y+.2],[x-.2,y+.2]], 'in_intersection': inside,
            'turning_left': inside, 'native_actor_id': actor}


class PhysicalAuditTest(unittest.TestCase):
    def test_lifecycle_rejects_saved_processing_before_release(self):
        self.assertTrue(module.validate_lifecycle(module.LIFECYCLE))
        with self.assertRaisesRegex(ValueError, 'owner release'):
            module.validate_lifecycle(module.LIFECYCLE[:-2] +
                                      tuple(reversed(module.LIFECYCLE[-2:])))

    def test_complete_incomplete_and_missing_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = [row(1,-2,0,False,1), row(2,0,0,True,1),
                 row(3,1,0,True,1), row(4,3,0,False,1)]
            b = [row(1,2,1,False,2), row(2,1,1,True,2),
                 row(3,0,1,True,2), row(4,-2,1,False,2)]
            for name, data in [('subject_original.jsonl', a), ('opposing_original.jsonl', b)]:
                (root/name).write_text(''.join(json.dumps(v)+'\n' for v in data))
            (root/'topology_original.json').write_text(json.dumps({
                'both_highways_two_directional': True, 'same_intersection': True,
                'opposing_approaches': True}))
            (root/'devices_original.json').write_text('{"governing_device":"none"}')
            paths = [root/n for n in ('subject_original.jsonl','opposing_original.jsonl',
                                     'topology_original.json','devices_original.json')]
            self.assertEqual(module.assess(*paths)['physical_checks']['maneuver']['status'], 'not_met')
            complete = module.assess(*paths, source_kind='native')
            self.assertEqual(complete['physical_checks']['maneuver']['status'], 'met')
            self.assertTrue(complete['maneuver_completed'])
            b[-1]['in_intersection'] = True
            paths[1].write_text(''.join(json.dumps(v)+'\n' for v in b))
            self.assertEqual(module.assess(*paths, source_kind='native')['physical_checks']['maneuver']['status'], 'not_met')
            paths[1].unlink()
            self.assertEqual(module.assess(*paths, source_kind='native')['physical_checks']['maneuver']['status'], 'unverified')


if __name__ == '__main__':
    unittest.main()
