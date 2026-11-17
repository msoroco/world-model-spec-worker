import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from lifecycle_preparation import EVENTS, inspect

class LifecyclePreparationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.write('config.json',{'case_id':'case-a'})
        self.write('construction.json',{'case_id':'case-a'})
        (self.root/'runner.py').write_text('pass\n')
        (self.root/'trace.jsonl').write_text('{"frame":1}\n')
        self.sources={name:self.sha(name) for name in ('config.json','construction.json','runner.py','trace.jsonl')}
        self.revision={'construction_sha256':self.sha('construction.json'),'runner_sha256':self.sha('runner.py')}
        self.seal={'format':'worker-sealed-capture','provenance_kind':'native','diagnostic_fixture':False,
                   'events':EVENTS[:3],'restoration':{'restored':True},'sources':self.sources,
                   'native_revision':self.revision}
        self.write('capture-seal.json',self.seal)
        self.exit_record={'event':'native_exit','capture_seal_sha256':self.sha('capture-seal.json'),'native_revision':self.revision}
        self.write('native-exit.json',self.exit_record)
        self.owner={'event':'owner_released','operator_attested':True,
                    'native_construction_sha256':self.revision['construction_sha256'],
                    'native_exit_sha256':self.sha('native-exit.json')}
        self.write('owner-release.json',self.owner)
        self.processing={'format':'worker-saved-processing','case_id':'case-a',
                         'recorded_only':True,'passed':True,'originals_preserved':True,
                         'original_source_hashes':self.sources,
                         'events':['saved_processing_started','selected_analysis_executed','originals_verified']}
        self.write('processing.json',self.processing)
    def write(self,name,value):
        (self.root/name).write_text(json.dumps(value)+'\n')
    def sha(self,name):
        return hashlib.sha256((self.root/name).read_bytes()).hexdigest()
    def check(self):
        return inspect(self.root,self.root/'owner-release.json',self.root/'processing.json')
    def test_bound_order_contract(self):
        self.assertEqual(self.check()['events'],EVENTS)
    def test_missing_owner_release_rejected(self):
        (self.root/'owner-release.json').unlink()
        with self.assertRaisesRegex(ValueError,'Missing lifecycle source'):
            self.check()
    def test_stale_source_and_early_processing_rejected(self):
        (self.root/'trace.jsonl').write_text('{"frame":2}\n')
        with self.assertRaisesRegex(ValueError,'Sealed original source changed'):
            self.check()
        (self.root/'trace.jsonl').write_text('{"frame":1}\n')
        self.processing['events']=['selected_analysis_executed','saved_processing_started']
        self.write('processing.json',self.processing)
        with self.assertRaisesRegex(ValueError,'Saved-only processing receipt differs'):
            self.check()
    def test_stale_exit_and_unattested_release_rejected(self):
        self.exit_record['capture_seal_sha256']='0'*64
        self.write('native-exit.json',self.exit_record)
        with self.assertRaisesRegex(ValueError,'Native exit receipt differs'):
            self.check()
        self.exit_record['capture_seal_sha256']=self.sha('capture-seal.json')
        self.write('native-exit.json',self.exit_record)
        self.owner['operator_attested']=False
        self.write('owner-release.json',self.owner)
        with self.assertRaisesRegex(ValueError,'Operator owner release'):
            self.check()
if __name__=='__main__':unittest.main()
