import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from delivery_audit import CAMERAS,audit_delivery

CASE='testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    def test_source_bound_review_and_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'trace.jsonl').write_text(json.dumps({'frame':100,'time_s':.05})+'\n')
            (root/'video_frames.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':100,'time_s':.05})+'\n')
            native={'case_id':CASE,'diagnostic_fixture':False,'trace_reference':'trace.jsonl',
                    'video_frame_map_reference':'video_frames.jsonl',
                    'video_references':[name+'.mkv' for name in CAMERAS]}
            (root/'result.json').write_text(json.dumps(native))
            camera_hashes={name:'a'*64 for name in CAMERAS}
            saved={'frame_count':1,'cameras':{name:{'sha256':value} for name,value in camera_hashes.items()}}
            review={'format':'c10307-independent-physical-review-v1','case_id':CASE,
                    'native_result_sha256':sha(root/'result.json'),
                    'video_frame_map_sha256':sha(root/'video_frames.jsonl'),
                    'videos':camera_hashes,'reviewer':'fixture reviewer','review_source':'unit-test-only',
                    'checks':{key:True for key in ('actual_bicycle_pixels','rack_visible',
                         'human_powered_bicycle_classification','municipal_jurisdiction',
                         'physical_route_completion','full_episode_coverage')}}
            rp=root/'review.json';rp.write_text(json.dumps(review))
            with patch('delivery_audit.audit_saved',return_value=saved):
                receipt=audit_delivery(root,CASE,rp)
                self.assertEqual(receipt['frame_count'],1)
                review['checks']['rack_visible']=False
                rp.write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError,'physical review'):
                    audit_delivery(root,CASE,rp)
                review['checks']['rack_visible']=True
                review['native_result_sha256']='0'*64
                rp.write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError,'absent or stale'):
                    audit_delivery(root,CASE,rp)
                native['diagnostic_fixture']=True
                (root/'result.json').write_text(json.dumps(native))
                with self.assertRaisesRegex(ValueError,'non-diagnostic'):
                    audit_delivery(root,CASE,rp)


if __name__=='__main__':unittest.main()
