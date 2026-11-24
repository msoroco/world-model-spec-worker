import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('saved_measurement',ROOT/'saved_measurement.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SavedMeasurementTests(unittest.TestCase):
    def fixture(self,root):
        (root/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True}))
        scene=json.loads((ROOT/'cases'/'outside_right_angle'/'scene.json').read_text())
        (root/'scene.json').write_text(json.dumps(scene))
        rows=[{'frame':i+100,'time_s':i*.05,'source':'original_native','actor_id':7,
               'body_center_xy_m':[5,i]} for i in range(7)]
        joins=[{'frame':r['frame'],'time_s':r['time_s'],
                'cameras':{name:i for name in ('overview','approach','reference_corner','driver_reference')}} for i,r in enumerate(rows)]
        (root/'walker-body-history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (root/'camera-frame-joins.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in joins))
        for name in ('overview','approach','reference_corner','driver_reference'):
            (root/(name+'.mkv')).write_bytes(('synthetic source '+name).encode())
        index={name:{'kind':'diagnostic_fixture','sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()} for name in m.REQUIRED}
        (root/'acquisition.json').write_text(json.dumps(index))
        return index

    def test_read_source_hashes_and_reject_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);self.fixture(root)
            out=m.read_attempt(root)
            self.assertEqual(out['measurement']['original_frame_count'],7)
            self.assertFalse(out['legal_verdict_claimed'])
            self.assertTrue(out['diagnostic_fixture'])
            (root/'overview.mkv').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'source hash mismatch: overview.mkv'):
                m.read_attempt(root)

    def test_missing_walker_source_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);self.fixture(root)
            (root/'walker-body-history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: walker-body-history.jsonl'):
                m.read_attempt(root)

    def test_native_source_cannot_use_short_center_only_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)
            index=self.fixture(root)
            marker={'provenance_kind':'native','diagnostic_fixture':False}
            (root/'acquisition-provenance.json').write_text(json.dumps(marker)+'\n')
            for binding in index.values():
                binding['kind']='original_native'
            (root/'acquisition.json').write_text(json.dumps(index)+'\n')
            with self.assertRaisesRegex(ValueError,'complete original walker body duration'):
                m.read_attempt(root)

if __name__=='__main__': unittest.main()
