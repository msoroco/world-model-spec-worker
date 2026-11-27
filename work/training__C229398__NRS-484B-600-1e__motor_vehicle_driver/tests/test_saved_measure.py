"""CPU source review rejects invented original scope and stale hashes."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from road_geometry import road_xml
from source_review import AID,SOURCES,join


class SourceReviewTests(unittest.TestCase):
    def test_synthetic_and_missing_original_scope(self):
        base=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            root=Path(tmp)
            (root/'source_context').mkdir()
            (root/'road.xodr').write_text(road_xml()+'\n')
            refs={}
            for name in SOURCES:
                path=root/'source_context'/(name+'.txt')
                path.write_text('Synthetic diagnostic '+name+'\n')
                refs[name]={'path':'source_context/'+name+'.txt',
                            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            case=AID+'__probe_01'
            review={'assignment_id':AID,'case_id':case,
                    'review_kind':'synthetic_diagnostic','sources':refs,
                    'road_xodr_sha256':hashlib.sha256((root/'road.xodr').read_bytes()).hexdigest(),
                    'physical_acceptance_claimed':False}
            (root/'approach-review.json').write_text(json.dumps(review)+'\n')
            self.assertFalse(join(root,case,diagnostic=True)['original_scope_reviewed'])
            with self.assertRaisesRegex(ValueError,'Synthetic source'):
                join(root,case,diagnostic=False)
            review['review_kind']='original_native'
            (root/'approach-review.json').write_text(json.dumps(review)+'\n')
            with self.assertRaisesRegex(ValueError,'Original source review incomplete'):
                join(root,case,diagnostic=False)
            review['review_kind']='synthetic_diagnostic'
            review['sources']['approach_scope']['sha256']='0'*64
            (root/'approach-review.json').write_text(json.dumps(review)+'\n')
            with self.assertRaisesRegex(ValueError,'Source hash mismatch'):
                join(root,case,diagnostic=True)
