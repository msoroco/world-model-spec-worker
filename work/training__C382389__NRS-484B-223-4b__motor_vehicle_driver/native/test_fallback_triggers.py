"""Synthetic source packets test both 4(b) lanes and three fallback gates."""
import json
from pathlib import Path
import tempfile
import unittest

from fallback_triggers import evaluate,sha


def row(frame,x,y,road,lane):
    return {'native_frame':frame,'time_s':frame/20,'native_center_xy_m':[x,y],
            'native_forward_xy':[1,0],'native_road_id':road,'native_lane_id':lane,
            'native_body_xy_m':[[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]]}


class FallbackTriggerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.samples=self.root/'native_samples.jsonl';self.geometry=self.root/'road_geometry.json'
        self.mapping=self.root/'map-audit.json';self.pixels=self.root/'pixel-audit.json'
        self.video=self.root/'overview.mkv';self.video.write_bytes(b'synthetic pixels')
        self.geometry.write_text(json.dumps({'native_map_sha256':'a'*64}))

    def write(self,lane,deviation=0,complete=True,link=True,visible=19):
        y=5.25 if lane==-2 else 1.75
        route=[[-20,y],[20,y]]
        rows=[row(1,-20,y,1,lane),row(2,-8,y+deviation,1,lane),
              row(3,-5,y,14,lane),row(4,15 if complete else 6,y,2 if complete else 14,lane)]
        self.samples.write_text(''.join(json.dumps(value)+'\n' for value in rows))
        self.mapping.write_text(json.dumps({'source_kind':'synthetic_map_readback',
            'connected_requested_lane_link':link,'native_map_sha256':'a'*64,
            'native_samples_sha256':sha(self.samples),'road_geometry_sha256':sha(self.geometry)}))
        self.pixels.write_text(json.dumps({'source_kind':'synthetic_camera_pixels',
            'native_samples_sha256':sha(self.samples),'video_sha256':sha(self.video),
            'full_body_and_lane_marking_visible_frames':visible,'approach_frames':20}))
        return route

    def measure(self,lane,route):
        return evaluate(self.samples,self.geometry,self.mapping,self.pixels,self.video,
                        route,lane)

    def test_distinct_thresholds_for_both_lanes(self):
        for lane in (-2,-1):
            with self.subTest(lane=lane):
                route=self.write(lane)
                self.assertEqual([self.measure(lane,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,False])
                route=self.write(lane,link=False)
                self.assertEqual([self.measure(lane,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [True,False,False])
                route=self.write(lane,complete=False)
                self.assertTrue(self.measure(lane,route)['fallback1'])
                route=self.write(lane,deviation=.36)
                self.assertEqual([self.measure(lane,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,True,False])
                route=self.write(lane,visible=18)
                self.assertEqual([self.measure(lane,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,True])

    def test_changed_source_and_provenance_rejected(self):
        route=self.write(-2)
        self.samples.write_text(self.samples.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Native map audit source hash mismatch'):
            self.measure(-2,route)
        route=self.write(-2)
        self.video.write_bytes(b'changed synthetic pixels')
        with self.assertRaisesRegex(ValueError,'Pixel audit source hash mismatch'):
            self.measure(-2,route)
        route=self.write(-2)
        self.geometry.write_text(json.dumps({'native_map_sha256':'b'*64}))
        with self.assertRaisesRegex(ValueError,'Native map audit source hash mismatch'):
            self.measure(-2,route)

    def test_mixed_provenance_rejected(self):
        route=self.write(-2)
        packet=json.loads(self.pixels.read_text())
        packet['source_kind']='original_camera_pixels'
        self.pixels.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError,'Trigger source provenance mismatch'):
            self.measure(-2,route)


if __name__=='__main__':unittest.main()
