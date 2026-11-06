"""Synthetic source packets test both 4(a) movements and three fallback gates."""
import json
from pathlib import Path
import tempfile
import unittest

from fallback_triggers import evaluate,sha


def row(frame,x,y,road,forward):
    return {'native_frame':frame,'time_s':frame/20,'native_center_xy_m':[x,y],
            'native_forward_xy':forward,'native_road_id':road,'native_lane_id':-2,
            'native_body_xy_m':[[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]]}


class FallbackTriggerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.samples=self.root/'native_samples.jsonl';self.geometry=self.root/'road_geometry.json'
        self.mapping=self.root/'map-audit.json';self.pixels=self.root/'pixel-audit.json'
        self.video=self.root/'overview.mkv';self.video.write_bytes(b'synthetic pixels')
        self.geometry.write_text(json.dumps({'native_map_sha256':'a'*64}))

    def write(self,movement,deviation=0,complete=True,link=True,visible=19):
        if movement=='right_turn':
            final=row(4,-5,12 if complete else 6,4 if complete else 13,[0,1])
            route=[[-20,5.25],[-5,5.25],[-5,12]]
            connector=13
        else:
            final=row(4,15 if complete else 6,5.25,2 if complete else 14,[1,0])
            route=[[-20,5.25],[20,5.25]]
            connector=14
        rows=[row(1,-20,5.25,1,[1,0]),row(2,-8,5.25+deviation,1,[1,0]),
              row(3,-5,5.25,connector,[1,0]),final]
        self.samples.write_text(''.join(json.dumps(value)+'\n' for value in rows))
        self.mapping.write_text(json.dumps({'source_kind':'native_map_readback',
            'connected_requested_lane_link':link,'native_map_sha256':'a'*64,
            'native_samples_sha256':sha(self.samples),'road_geometry_sha256':sha(self.geometry)}))
        self.pixels.write_text(json.dumps({'source_kind':'original_camera_pixels',
            'native_samples_sha256':sha(self.samples),'video_sha256':sha(self.video),
            'full_body_and_lane_marking_visible_frames':visible,'approach_frames':20}))
        return route

    def measure(self,movement,route):
        return evaluate(self.samples,self.geometry,self.mapping,self.pixels,self.video,
                        route,movement)

    def test_distinct_thresholds_for_turn_and_straight(self):
        for movement in ('right_turn','straight_through'):
            with self.subTest(movement=movement):
                route=self.write(movement)
                self.assertEqual([self.measure(movement,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,False])
                route=self.write(movement,link=False)
                self.assertEqual([self.measure(movement,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [True,False,False])
                route=self.write(movement,complete=False)
                self.assertTrue(self.measure(movement,route)['fallback1'])
                route=self.write(movement,deviation=.36)
                self.assertEqual([self.measure(movement,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,True,False])
                route=self.write(movement,visible=18)
                self.assertEqual([self.measure(movement,route)[f'fallback{i}'] for i in (1,2,3)],
                                 [False,False,True])

    def test_changed_source_and_provenance_rejected(self):
        route=self.write('right_turn')
        self.samples.write_text(self.samples.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Native map audit source hash mismatch'):
            self.measure('right_turn',route)
        route=self.write('right_turn')
        self.video.write_bytes(b'changed synthetic pixels')
        with self.assertRaisesRegex(ValueError,'Pixel audit source hash mismatch'):
            self.measure('right_turn',route)
        route=self.write('right_turn')
        self.geometry.write_text(json.dumps({'native_map_sha256':'b'*64}))
        with self.assertRaisesRegex(ValueError,'Native map audit source hash mismatch'):
            self.measure('right_turn',route)


if __name__=='__main__':unittest.main()
