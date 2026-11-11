import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from test_measurements import sources
spec=importlib.util.spec_from_file_location('c109749_finalizer',ROOT/'finalizer.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FinalizerTests(unittest.TestCase):
    def fixture(self,root):
        sources(root)
        config=json.loads((ROOT/'config.json').read_text())
        (root/'config.json').write_text(json.dumps(config))
        rows=[json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines()]
        (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':row['frame'],
                'time_s':row['time_s'],'heading_deg':row['ego_heading_deg']})+'\n' for row in rows))
        (root/'capture').mkdir()
        (root/'capture/evidence.jsonl').write_text(json.dumps({'diagnostic_fixture':True})+'\n')
        for name in module.CAMERAS:
            (root/name).write_bytes(b'diagnostic-placeholder')

    def test_saved_sources_rebuild_channels_and_keep_legal_judgment_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            report=module.finalize(root,root/'analysis.json')
            result=json.loads((root/'result.json').read_text())
            self.assertEqual(report['format'],'worker-left-turn-analysis')
            self.assertFalse(report['legal_verdict_asserted'])
            self.assertTrue(result['measured_values']['reciprocal_stopped_outside_during_turn'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertTrue(result['diagnostic_fixture'])
            self.assertEqual(len((root/'channels/reciprocal_speed.jsonl').read_text().splitlines()),4)
            self.assertIn('physical_checks',result)

    def test_missing_original_interaction_history_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root)
            (root/'interaction_history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: interaction_history.jsonl'):
                module.finalize(root,root/'analysis.json')


if __name__=='__main__':
    unittest.main()
