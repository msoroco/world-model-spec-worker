import json
import tempfile
import unittest
from pathlib import Path
from update002_saved_index import build

class SavedIndexTests(unittest.TestCase):
    def test_exact_processing_revision_is_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);repo=root/'repo';out=root/'processed';aid='testing__C1__LAW__driver';cid=aid+'__case'
            folder=repo/'work'/aid;folder.mkdir(parents=True)
            manifest={'assignment_id':aid,'runtime_manifest_sha256':'runtime',
                      'cases':[{'case_id':cid,'construction_sha256':'primary',
                                'candidates':[{'id':'fallback1','construction_sha256':'fallback'}]}]}
            (folder/'execution-manifest.json').write_text(json.dumps(manifest))
            version=out/aid/cid/'v0001';stage=version/'analysis';stage.mkdir(parents=True)
            (stage/'analysis-report.json').write_text('{}');(stage/'config.json').write_text('{}')
            receipt={'case_id':cid,'passed':True,'originals_preserved':True,
                     'analysis_directory':str(stage),'analysis_revision':{'construction_sha256':'fallback',
                     'runtime_manifest_sha256':'runtime'},'native_revision':{'construction_sha256':'fallback'}}
            (version/'processing.json').write_text(json.dumps(receipt))
            self.assertEqual(build(repo,out)['cases_indexed'],1)
            index=json.loads((out/aid/'native-comparison-index.json').read_text())
            self.assertEqual(index[cid]['analysis_revision']['construction_sha256'],'fallback')
            receipt['analysis_revision']['runtime_manifest_sha256']='stale'
            (version/'processing.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'No exact saved analysis'):
                build(repo,out)
if __name__=='__main__':unittest.main()
