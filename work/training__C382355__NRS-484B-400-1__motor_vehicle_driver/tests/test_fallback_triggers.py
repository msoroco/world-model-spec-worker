import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fallback_triggers import evaluate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(frame, x, y, road, lane):
    return {'native_frame': frame, 'time_s': frame / 20,
            'native_center_xy_m': [x, y], 'native_road_id': road, 'native_lane_id': lane,
            'native_body_xy_m': [[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]]}


class FallbackTriggersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.samples = root/'native_samples.jsonl'
        self.mapping = root/'map-audit.json'
        self.pixels = root/'pixel-audit.json'
        self.video = root/'overview.mkv'
        self.video.write_bytes(b'synthetic camera fixture')
        self.route = [[-20,5.25],[-5,5.25],[-5,12]]
        self.write()

    def write(self, deviation=0, exit=True, link=True, visible=19, total=20):
        rows = [row(1,-20,5.25,1,-2), row(2,-8,5.25+deviation,1,-2),
                row(3,-5,5.25,13,-2),row(4,-5,12 if exit else 6,4 if exit else 13,-2)]
        self.samples.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.mapping.write_text(json.dumps({'source_kind':'synthetic_map_readback',
            'native_samples_sha256':sha(self.samples),'connected_right_turn_lane_link':link}))
        self.pixels.write_text(json.dumps({'source_kind':'synthetic_camera_pixels',
            'native_samples_sha256':sha(self.samples),'video_sha256':sha(self.video),
            'full_body_and_lane_marking_visible_frames':visible,'approach_frames':total}))

    def measure(self):
        return evaluate(self.samples,self.mapping,self.pixels,self.video,self.route)

    def test_measured_thresholds_and_distinct_fallbacks(self):
        base=self.measure()
        self.assertFalse(any(base[name] for name in ('fallback1','fallback2','fallback3')))
        self.assertEqual(base['metrics']['approach_pixel_visible_fraction'],.95)
        self.write(link=False)
        self.assertEqual([self.measure()[n] for n in ('fallback1','fallback2','fallback3')],[True,False,False])
        self.write(exit=False)
        self.assertEqual([self.measure()[n] for n in ('fallback1','fallback2','fallback3')],[True,False,False])
        self.write(deviation=.36)
        self.assertEqual([self.measure()[n] for n in ('fallback1','fallback2','fallback3')],[False,True,False])
        self.write(visible=18)
        self.assertEqual([self.measure()[n] for n in ('fallback1','fallback2','fallback3')],[False,False,True])

    def test_source_tampering_rejected(self):
        self.video.write_bytes(b'changed synthetic camera fixture')
        with self.assertRaisesRegex(ValueError,'Pixel audit source hash mismatch'):
            self.measure()
        self.video.write_bytes(b'synthetic camera fixture')
        self.samples.write_text(self.samples.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Native sample hash mismatch'):
            self.measure()

    def test_mixed_provenance_rejected(self):
        packet=json.loads(self.pixels.read_text())
        packet['source_kind']='original_camera_pixels'
        self.pixels.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError,'Trigger source provenance mismatch'):
            self.measure()


if __name__=='__main__': unittest.main()
