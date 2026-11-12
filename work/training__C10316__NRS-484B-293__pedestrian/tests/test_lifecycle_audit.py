"""Source-shaped verifier tests; no CARLA speed, media or delivery receipt."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifecycle_audit import CAMERAS, EVENTS, audit, sha


class LifecycleAuditTests(unittest.TestCase):
    def shape(self, root):
        attempt = root / 'attempt'; attempt.mkdir()
        saved = root / 'saved/v0001'; (saved / 'analysis').mkdir(parents=True)
        for name in ('runner.py', 'construction.json', 'native_samples.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                     'video_frames.jsonl', 'capture/native/frames.jsonl',
                     'crosswalk-context.json', 'capture/manifest.json', *(camera + '.mkv' for camera in CAMERAS)):
            (attempt / name).parent.mkdir(parents=True, exist_ok=True)
            (attempt / name).write_text('source-shaped unit test: ' + name)
        construction = sha(attempt / 'construction.json')
        sources = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
        seal = {'format':'worker-sealed-capture', 'provenance_kind':'native',
                'diagnostic_fixture':False, 'source_shaped_unit_test':True,
                'frames':240, 'events':EVENTS[:3],
                'restoration':{'restored':True},
                'encoder_exit_codes':{camera:0 for camera in CAMERAS},
                'native_revision':{'construction_sha256':construction,
                                   'runner_sha256':sha(attempt/'runner.py')},
                'sources':sources}
        (attempt / 'capture-seal.json').write_text(json.dumps(seal))
        exit_record = {'event':'native_exit','native_process_exit_code':0,
                       'capture_seal_sha256':sha(attempt/'capture-seal.json'),
                       'native_revision':seal['native_revision']}
        (attempt / 'native-exit.json').write_text(json.dumps(exit_record))
        owner = root / 'owner.json'
        owner.write_text(json.dumps({'event':'owner_released',
            'operator_attested':True,'no_resource_operation_performed':True,
            'native_exit_sha256':sha(attempt/'native-exit.json'),
            'native_construction_sha256':construction}))
        result = saved / 'analysis/result.json'
        result.write_text(json.dumps({'case_id':'case','provenance_kind':'native_source_shape_unverified',
                                      'diagnostic_fixture':False,
                                      'source_shaped_unit_test':True}))
        processing = saved / 'processing.json'
        processing.write_text(json.dumps({'format':'worker-saved-processing',
            'source_shaped_unit_test':True,
            'case_id':'case','passed':True,'recorded_only':True,
            'originals_preserved':True,'native_revision':
            {'construction_sha256':construction},
            'events':['saved_processing_started','selected_analysis_executed',
                      'originals_verified'],
            'original_source_hashes':sources,'result':str(result),
            'result_sha256':sha(result)}))
        return attempt, owner, processing, construction

    def test_source_shaped_chain_and_negative_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt, owner, processing, construction = self.shape(root)
            proof = audit(attempt, owner, processing, 'case', construction,
                          test_shape=True)
            self.assertEqual(proof['events'], EVENTS)
            self.assertEqual(proof['exit_code'], 0)
            # The selected finalizer omits this optional field on a real run.
            result = root / 'saved/v0001/analysis/result.json'
            value = json.loads(result.read_text())
            value.pop('diagnostic_fixture')
            result.write_text(json.dumps(value))
            receipt = json.loads(processing.read_text())
            receipt['result_sha256'] = sha(result)
            processing.write_text(json.dumps(receipt))
            self.assertEqual(audit(attempt, owner, processing, 'case', construction,
                                   test_shape=True)
                             ['events'], EVENTS)
            with self.assertRaisesRegex(ValueError, 'Source-shaped unit test'):
                audit(attempt, owner, processing, 'case', construction)
            # The shape test never writes a physical preparation receipt.
            value = json.loads(owner.read_text())
            value['native_exit_sha256'] = '0' * 64
            owner.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'Owner release'):
                audit(attempt, owner, processing, 'case', construction,
                      test_shape=True)

    def test_synthetic_or_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt, owner, processing, construction = self.shape(root)
            result = root / 'saved/v0001/analysis/result.json'
            value = json.loads(result.read_text())
            value['provenance_kind'] = 'synthetic_local_diagnostic'
            result.write_text(json.dumps(value))
            value = json.loads(processing.read_text())
            value['result_sha256'] = sha(result)
            processing.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'synthetic'):
                audit(attempt, owner, processing, 'case', construction,
                      test_shape=True)
            (attempt / 'native_samples.jsonl').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Sealed original source changed'):
                audit(attempt, owner, processing, 'case', construction,
                      test_shape=True)


if __name__ == '__main__':
    unittest.main()
