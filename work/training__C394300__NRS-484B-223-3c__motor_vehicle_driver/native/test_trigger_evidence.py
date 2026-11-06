"""Source-bound CPU fallback checks on synthetic original-shaped attempts."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_measure_after_turn import GEOMETRY,fixture,row
from trigger_evidence import evaluate


class TriggerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.folder=Path(self.scratch.name)
        inbound=row(1,-71.75,25,road=4,heading=(0,-1))
        self.rows=[inbound]+[{**item,'native_frame':item['native_frame']+2,
                              'time_s':(item['native_frame']+2)/20,
                              'controller_request':{'route_error_m':.1}}
                             for item in fixture(45)]
        inbound['controller_request']={'route_error_m':.1}
        (self.folder/'road_geometry.json').write_text(json.dumps(GEOMETRY))
        self.save()

    def save(self):
        (self.folder/'native_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))

    def test_inbound_containment_positive_and_negative(self):
        normal=evaluate(self.folder,'fallback1')
        self.assertFalse(normal['triggered'])
        self.assertEqual(normal['metric']['inbound_body_containment_fraction'],1)
        self.rows[0]['native_body_xy_m'][0][0]=-75
        self.save()
        self.assertTrue(evaluate(self.folder,'fallback1')['triggered'])

    def test_route_error_positive_and_negative(self):
        self.assertFalse(evaluate(self.folder,'fallback2')['triggered'])
        self.rows[5]['controller_request']['route_error_m']=.36
        self.save()
        self.assertTrue(evaluate(self.folder,'fallback2')['triggered'])
        del self.rows[5]['controller_request']['route_error_m']
        self.save()
        with self.assertRaisesRegex(ValueError,'route_error_m'):
            evaluate(self.folder,'fallback2')

    def test_pixel_annotations_require_hashed_complete_original_sources(self):
        names=('overview','approach','reference_corner','driver_reference')
        hashes={}
        for name in names:
            video=self.folder/(name+'.mkv')
            video.write_bytes(('synthetic-'+name).encode())
            hashes[name]=hashlib.sha256(video.read_bytes()).hexdigest()
        audit={'independent_original_pixel_review':True,'source_video_sha256':hashes,
               'frames':[{'native_frame':r['native_frame'],'marking_visible':True,
                          'body_visible':True} for r in self.rows]}
        path=self.folder/'pixel_visibility_audit.json'
        path.write_text(json.dumps(audit))
        self.assertFalse(evaluate(self.folder,'fallback3')['triggered'])
        for flag in audit['frames'][:max(1,len(self.rows)//10)]:
            flag['marking_visible']=False
        path.write_text(json.dumps(audit))
        self.assertTrue(evaluate(self.folder,'fallback3')['triggered'])
        (self.folder/'overview.mkv').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'video hash differs'):
            evaluate(self.folder,'fallback3')


if __name__=='__main__':unittest.main()
