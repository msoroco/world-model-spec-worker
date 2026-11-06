"""Synthetic 480-frame positive, controlled straight and source rejection tests."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from measure_u_turn import measure,sha
from geometry import native_route


class UTurnMeasurementTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.samples=self.root/'native_samples.jsonl'
        self.mapping=self.root/'video_frames.jsonl'
        self.review=self.root/'sign-review.json'
        self.pixel_review=self.root/'pixel_review.jsonl'
        self.video=self.root/'approach-video-fixture.txt'
        self.video.write_bytes(b'synthetic 480-frame camera placeholder')

    def write(self, turn=True, governed=True):
        samples=[];mapping=[]
        route=native_route('witness_2' if turn else 'witness_1')
        for i in range(480):
            frame=100+i;time=(i+1)/20
            station=round(i*(len(route)-1)/479)
            x,y=route[station]
            before=route[max(0,station-2)];after=route[min(len(route)-1,station+2)]
            angle=math.atan2(after[1]-before[1],after[0]-before[0])
            lane=1 if turn and station>700 else -1
            forward=(math.cos(angle),math.sin(angle))
            right=(-forward[1],forward[0])
            body=[[x+a*forward[0]+b*right[0],y+a*forward[1]+b*right[1]]
                  for a,b in ((-2.5,-1),(-2.5,1),(2.5,1),(2.5,-1))]
            samples.append({'native_frame':frame,'time_s':time,
                'native_center_xy_m':[x,y],
                'native_forward_xy':list(forward),
                'native_body_xy_m':body,'native_road_id':1,'native_lane_id':lane})
            mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':time})
        self.samples.write_text(''.join(json.dumps(row)+'\n' for row in samples))
        self.mapping.write_text(''.join(json.dumps(row)+'\n' for row in mapping))
        approach=[i for i,row in enumerate(samples) if -35<=row['native_center_xy_m'][0]<=-10]
        self.pixel_review.write_text(''.join(json.dumps({
            'video_frame':i,'native_frame':mapping[i]['native_frame'],
            'full_body_visible':True,'sign_visible':True})+'\n' for i in approach))
        self.review.write_text(json.dumps({'source_kind':'original_camera_sign_review',
            'sign_code':'no_u_turn','governs_approach':governed,
            'governed_approach_lane_id':-1,'opposing_lane_id':1,
            'full_body_and_sign_visible_frames':len(approach),'approach_frames':len(approach),
            'governed_native_xy_bounds_m':[-10,-8,10,8],
            'native_samples_sha256':sha(self.samples),'frame_map_sha256':sha(self.mapping),
            'video_sha256':sha(self.video),'pixel_review_sha256':sha(self.pixel_review)}))

    def test_controlled_signed_pair(self):
        self.write(turn=False)
        straight=measure(self.samples,self.mapping,self.review,self.video)
        self.write(turn=True)
        turning=measure(self.samples,self.mapping,self.review,self.video)
        self.assertFalse(straight['u_turn_within_governed_region_observed'])
        self.assertTrue(turning['u_turn_within_governed_region_observed'])
        self.assertIsNotNone(turning['reversal_native_frame'])
        self.assertTrue(turning['opposing_lane_exit_observed'])
        self.assertFalse(turning['physical_success_claimed'])
        self.assertFalse(turning['legal_verdict_claimed'])

    def test_changed_video_rejected(self):
        self.write();self.video.write_bytes(b'changed pixels')
        with self.assertRaisesRegex(ValueError,'source hash'):
            measure(self.samples,self.mapping,self.review,self.video)

    def test_changed_native_source_rejected(self):
        self.write();self.samples.write_text(self.samples.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'source hash'):
            measure(self.samples,self.mapping,self.review,self.video)

    def test_missing_sign_applicability_rejected(self):
        self.write(governed=False)
        with self.assertRaisesRegex(ValueError,'device unverified'):
            measure(self.samples,self.mapping,self.review,self.video)

    def test_reversal_outside_governed_region_not_counted(self):
        self.write(turn=True)
        review=json.loads(self.review.read_text())
        review['governed_native_xy_bounds_m']=[-10,-8,-2.5,8]
        self.review.write_text(json.dumps(review))
        result=measure(self.samples,self.mapping,self.review,self.video)
        self.assertFalse(result['u_turn_within_governed_region_observed'])
        self.assertIsNotNone(result['reversal_native_frame'])

    def test_frame_join_mismatch_rejected(self):
        self.write();rows=self.mapping.read_text().splitlines()
        row=json.loads(rows[20]);row['carla_frame']=9;rows[20]=json.dumps(row)
        self.mapping.write_text('\n'.join(rows)+'\n')
        review=json.loads(self.review.read_text());review['frame_map_sha256']=sha(self.mapping)
        self.review.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError,'frame join|frame identity'):
            measure(self.samples,self.mapping,self.review,self.video)

    def test_changed_pixel_mark_rejected(self):
        self.write()
        marks=self.pixel_review.read_text().splitlines()
        mark=json.loads(marks[10]);mark['sign_visible']=False;marks[10]=json.dumps(mark)
        self.pixel_review.write_text('\n'.join(marks)+'\n')
        with self.assertRaisesRegex(ValueError,'Pixel review source hash'):
            measure(self.samples,self.mapping,self.review,self.video)

    def test_rehashed_pixel_count_mismatch_rejected(self):
        self.write()
        marks=self.pixel_review.read_text().splitlines()
        mark=json.loads(marks[10]);mark['sign_visible']=False;marks[10]=json.dumps(mark)
        self.pixel_review.write_text('\n'.join(marks)+'\n')
        review=json.loads(self.review.read_text());review['pixel_review_sha256']=sha(self.pixel_review)
        self.review.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError,'count differs'):
            measure(self.samples,self.mapping,self.review,self.video)


if __name__=='__main__':unittest.main()
