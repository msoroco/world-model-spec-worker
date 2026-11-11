"""Source-bound auditor mechanics with synthetic rows; no original claim."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('c132497_delivery_audit',
    ROOT/'native/delivery_audit.py')
AUDIT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def sample(lane=-2):
    raw=[];frames=[];trace=[]
    for i in range(240):
        t=(i+1)/20
        road=20 if i<30 else 21 if i<210 else 22
        raw.append({'frame':i,'native_frame':1000+i,'time_s':t,
            'source_kind':'synthetic_native_sample','observed_road_id':road,
            'observed_lane_id':lane,'ego':{'actor_id':7,
                'center_native_xyz_m':[float(i),0.0,0.0],
                'speed_mps':5.0}})
        frames.append({'video_frame':i,'carla_frame':1000+i,
                       'native_frame':1000+i,'time_s':t})
        trace.append({'frame':1000+i,'time_s':t})
    return raw,frames,trace


class DeliveryAuditorMechanics(unittest.TestCase):
    def test_synthetic_row_join_and_exit(self):
        raw,frames,trace=sample()
        result=AUDIT.validate_rows(raw,frames,trace,
            AUDIT.ASSIGNMENT+'__reference','primary','synthetic_native_sample')
        self.assertEqual(result['exit_lane_id'],-2)
        self.assertEqual(result['frames'],240)

    def test_production_refuses_synthetic_provenance(self):
        raw,frames,trace=sample()
        with self.assertRaisesRegex(ValueError,'actor/frame/trace join differs'):
            AUDIT.validate_rows(raw,frames,trace,
                AUDIT.ASSIGNMENT+'__reference','primary')

    def test_changed_frame_join_rejected(self):
        raw,frames,trace=sample()
        frames[89]['native_frame']+=2
        with self.assertRaisesRegex(ValueError,'join differs at 89'):
            AUDIT.validate_rows(raw,frames,trace,
                AUDIT.ASSIGNMENT+'__reference','primary','synthetic_native_sample')

    def test_wrong_exit_lane_rejected(self):
        raw,frames,trace=sample(-1)
        with self.assertRaisesRegex(ValueError,'exit lane differs'):
            AUDIT.validate_rows(raw,frames,trace,
                AUDIT.ASSIGNMENT+'__reference','primary','synthetic_native_sample')

    def test_loop_before_first_exit_rejected(self):
        raw,frames,trace=sample()
        raw[150]['observed_road_id']=23
        with self.assertRaisesRegex(ValueError,'phases reverse or loop'):
            AUDIT.validate_rows(raw,frames,trace,
                AUDIT.ASSIGNMENT+'__reference','primary','synthetic_native_sample')

    def test_pixel_checker_positive_and_outside_negative(self):
        boxes=[{'claim':claim,'frame':i,'rect_xywh':[0,0,2,2]}
               for i,claim in enumerate(sorted(AUDIT.CLAIMS))]
        check,seen=AUDIT.pixel_checker(boxes,4)
        class Frame:
            width=3;height=3
            pixels=bytes(range(27))
            def __init__(self,index):self.index=index
        for i in range(4):check(Frame(i))
        self.assertEqual(seen,AUDIT.CLAIMS)
        bad=copy.deepcopy(boxes);bad[0]['rect_xywh']=[2,2,2,2]
        callback,_=AUDIT.pixel_checker(bad,4)
        with self.assertRaisesRegex(ValueError,'exceeds decoded video'):
            callback(Frame(0))

    def test_review_source_hash_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt=Path(tmp)
            names=['native-raw-actors.jsonl','native-map-readback.json',
                   'video_frames.jsonl','controller-intention.json','raw.mkv']
            names += [name+'.mkv' for name in AUDIT.CAMERAS]
            for name in names:(attempt/name).write_text(name)
            case=AUDIT.ASSIGNMENT+'__reference'
            boxes=[{'claim':claim,'frame':i,'rect_xywh':[0,0,2,2]}
                   for i,claim in enumerate(sorted(AUDIT.CLAIMS))]
            review={'source_kind':'original_native_review','reviewer_id':'mock-cpu-reviewer',
                'case_id':case,'candidate_id':'primary',
                'counterclockwise_roundabout_verified':True,
                'right_lane_identity_reviewed':True,
                'actual_right_exit_reviewed':True,
                'operator_and_jurisdiction_reviewed':True,
                'legal_verdict':None,'pixel_boxes':boxes,
                'sources':{name:AUDIT.sha(attempt/name) for name in names}}
            self.assertEqual(AUDIT.validate_review(review,case,'primary',attempt,
                attempt/'raw.mkv'),boxes)
            (attempt/'approach.mkv').write_text('changed')
            with self.assertRaisesRegex(ValueError,'source hash differs: approach.mkv'):
                AUDIT.validate_review(review,case,'primary',attempt,attempt/'raw.mkv')

    def test_real_full_decode_and_stale_receipt_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);video=tmp/'tiny.mkv';receipt=tmp/'decode.json'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                '-f','lavfi','-i','testsrc=size=8x8:rate=20',
                '-frames:v','4','-c:v','ffv1',str(video)],check=True)
            boxes=[{'claim':claim,'frame':i,'rect_xywh':[0,0,4,4]}
                   for i,claim in enumerate(sorted(AUDIT.CLAIMS))]
            callback,seen=AUDIT.pixel_checker(boxes,4)
            media=AUDIT.media_module()
            version=AUDIT.sha(ROOT/'native/delivery_audit.py')
            result=media.audit(video,4,checkers={'c132497_reviewed_pixels':
                (version,callback)},mapping_sha256='d'*64,receipt=receipt)
            self.assertEqual(result['frames'],4)
            self.assertEqual(seen,AUDIT.CLAIMS)
            self.assertEqual(media.verify_receipt(video,receipt,4,
                mapping_sha256='d'*64,required_checks={
                    'c132497_reviewed_pixels':version})['video_sha256'],AUDIT.sha(video))
            with self.assertRaisesRegex(ValueError,'Stale/incompatible source audit receipt'):
                media.verify_receipt(video,receipt,4,mapping_sha256='e'*64)


if __name__=='__main__':unittest.main()
