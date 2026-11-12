import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('space_physical_audit',ROOT/'space_physical_audit.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PhysicalAuditTest(unittest.TestCase):
    def test_complete_incomplete_missing_and_lifecycle(self):
        source=json.loads((ROOT/'diagnostic-crosswalk_clear_downstream.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            scene=Path(tmp)/'space_scene.json';frames=Path(tmp)/'space_frames.jsonl'
            scene.write_text(source['files']['space_scene.json'])
            frames.write_text(source['files']['space_frames.jsonl'])
            self.assertEqual(module.assess(scene,frames)['physical_checks']['maneuver']['status'],'not_met')
            self.assertEqual(module.assess(scene,frames,'native')['physical_checks']['maneuver']['status'],'met')
            rows=frames.read_text().splitlines()
            frames.write_text('\n'.join(rows[:4])+'\n')
            self.assertEqual(module.assess(scene,frames,'native')['physical_checks']['maneuver']['status'],'not_met')
            frames.unlink()
            self.assertEqual(module.assess(scene,frames,'native')['physical_checks']['maneuver']['status'],'unverified')
        self.assertTrue(module.validate_lifecycle(module.LIFECYCLE))
        with self.assertRaisesRegex(ValueError,'owner release'):
            module.validate_lifecycle(module.LIFECYCLE[:-2]+tuple(reversed(module.LIFECYCLE[-2:])))


if __name__=='__main__':
    unittest.main()
