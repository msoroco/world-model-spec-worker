import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fallback_triggers import evaluate_native,evaluate_pixels


class FallbackTriggersTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def samples(self,first_y=3.5,entry_time=2.0,error=0):
        rows=[]
        for frame,(time,x,y,lane) in enumerate(((.05,-95,first_y,-2),
                    (entry_time,-50,0,-1),(4,-40,0,-1)),1):
            y+=error
            rows.append({'native_frame':frame,'time_s':time,
                'native_center_xy_m':[x,y],
                'native_body_xy_m':[[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]],
                'native_road_id':1,'native_lane_id':lane})
        path=self.root/'native_samples.jsonl'
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return path

    def test_fallback1_positive_and_negative(self):
        self.assertFalse(evaluate_native(self.samples(),'witness_1')['fallback1']['triggered'])
        self.assertTrue(evaluate_native(self.samples(first_y=6),'witness_1')['fallback1']['triggered'])
        self.assertTrue(evaluate_native(self.samples(entry_time=3.5),'witness_1')['fallback1']['triggered'])

    def test_fallback2_positive_and_negative(self):
        self.assertFalse(evaluate_native(self.samples(),'witness_1')['fallback2']['triggered'])
        self.assertTrue(evaluate_native(self.samples(error=1),'witness_1')['fallback2']['triggered'])

    def test_pixel_annotations_bind_source_and_fail_closed(self):
        video=self.root/'approach.mkv';video.write_bytes(b'synthetic pixels')
        sha=hashlib.sha256(video.read_bytes()).hexdigest()
        annotations=self.root/'pixel-review.json'
        def write(visible=True,reviewed=True,digest=sha):
            annotations.write_text(json.dumps({'source_video_sha256':digest,
                'approach_frames':[{'frame':i,'original_pixels_reviewed':reviewed,
                'body_visible':True,'center_lane_marking_visible':visible} for i in range(20)]}))
        write();self.assertFalse(evaluate_pixels(annotations,video)['fallback3_triggered'])
        write(False);self.assertTrue(evaluate_pixels(annotations,video)['fallback3_triggered'])
        write(reviewed=False)
        with self.assertRaises(ValueError):evaluate_pixels(annotations,video)
        write(digest='0'*64)
        with self.assertRaises(ValueError):evaluate_pixels(annotations,video)


if __name__=='__main__':unittest.main()
