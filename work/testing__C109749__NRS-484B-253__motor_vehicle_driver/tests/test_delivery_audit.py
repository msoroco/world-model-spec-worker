"""Independent audit must reject missing or inconsistent original evidence."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c109749_delivery_audit',ROOT/'delivery_audit.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
CASE='testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn'


class OriginalSourceAudit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        source=Path('.runtime-work/c109749-primary-compat-v9')
        for name in ('config.json','intersection_geometry.json','video_frames.jsonl',
                     'interaction_history.jsonl','trace.jsonl'):
            shutil.copyfile(source/name,self.root/name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_diagnostic_join_and_full_duration_rejection(self):
        joined=audit.validate_originals(self.root,CASE,full_duration=False)
        self.assertEqual(joined['participant_ids'],[205,307,411])
        self.assertEqual(joined['frames'],9)
        with self.assertRaisesRegex(ValueError,'full planned duration'):
            audit.validate_originals(self.root,CASE)

    def test_missing_third_actor_rejected(self):
        path=self.root/'interaction_history.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        del rows[4]['reciprocal']
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError,'Missing complete participant: reciprocal'):
            audit.validate_originals(self.root,CASE,full_duration=False)

    def test_frame_join_and_missing_history_rejected(self):
        path=self.root/'interaction_history.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[3]['frame']+=1
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError,'frame/time join'):
            audit.validate_originals(self.root,CASE,full_duration=False)
        path.unlink()
        with self.assertRaisesRegex(ValueError,'Missing original source: interaction_history.jsonl'):
            audit.validate_originals(self.root,CASE,full_duration=False)

    def test_live_audit_rejects_diagnostic_result(self):
        source=Path('.runtime-work/c109749-primary-compat-v9')
        shutil.copyfile(source/'result.json',self.root/'result.json')
        with self.assertRaisesRegex(ValueError,'Non-diagnostic Native result required'):
            audit.audit_attempt(self.root,CASE,'job',1,'recording',self.root/'review.json',
                                self.root/'delivery-audit.json',self.root.parent/'decode.json')


if __name__=='__main__':unittest.main()
