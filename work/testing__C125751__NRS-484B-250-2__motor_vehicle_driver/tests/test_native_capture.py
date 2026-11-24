import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from entry_timing import ASSIGNMENT
from native_capture import CAMERAS, capture
from saved_delivery import audit

from test_entry_timing import body, survey


class Adapter:
    def __init__(self, *, drift=False, missing_camera=False):
        self.drift, self.missing_camera = drift, missing_camera
        self.index = 0
        self.output = None
        self.closed = False
        self.stopped = []
        self.destroyed = []
        stream = io.BytesIO()
        Image.new('RGB',(4,4),(20,40,60)).save(stream,format='PNG')
        self.png = stream.getvalue()

    def verify_map(self, surveyed, raw):
        if raw != b'original map':
            raise ValueError('map differs')

    def spawn_actors(self, surveyed, case_id):
        return {'ego': SimpleNamespace(id=10, name='ego'),
                'other': SimpleNamespace(id=11, name='other')}

    def configure_cameras(self, ego, channels, *, fps, output):
        if tuple(channels) != CAMERAS or fps != 20:
            raise ValueError('camera profile differs')
        self.output = output

    def request_controls(self, handles, case_id, index):
        self.index = index

    def tick(self):
        return 1000+self.index, 50+self.index/20+(.02 if self.drift and self.index == 10 else 0)

    def actor_snapshot(self, actor, frame):
        entry = 66 if actor.name == 'ego' else 60
        pos = -10 if self.index < entry else 0 if self.index < entry+10 else 10
        x,y = (0,pos) if actor.name == 'ego' else (pos,0)
        return {'id':actor.id,'road_id':1 if actor.name == 'ego' else 2,
                'body_vertices_xy_m':body(x,y)}

    def signal_readback(self, surveyed, frame):
        return 'inoperative'

    def camera_frame(self, channel, frame):
        if self.missing_camera and channel == 'right' and self.index == 10:
            raise ValueError('original camera missing')
        relative = Path('media')/channel/f'{frame}.png'
        path = self.output/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.png)
        return {'channel':channel,'frame':frame,'source_path':str(relative),
                'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def close_cameras(self):
        self.closed = True

    def emergency_stop(self, actor):
        self.stopped.append(actor.id)

    def destroy(self, actor):
        self.destroyed.append(actor.id)


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3]/'.runtime-work'/'c125751-native-tests'
        scratch.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.survey = survey()
        self.survey['opendrive_sha256'] = hashlib.sha256(b'original map').hexdigest()
        self.survey_path = self.root/'survey.json'
        self.survey_path.write_text(json.dumps(self.survey)+'\n')
        self.map_path = self.root/'original.xodr'
        self.map_path.write_bytes(b'original map')
        self.case = ASSIGNMENT+'__precedence'

    def run_capture(self, adapter):
        return capture(adapter,self.survey_path,
                       hashlib.sha256(self.survey_path.read_bytes()).hexdigest(),
                       self.map_path,self.case,self.root/'attempt')

    def test_complete_original_actor_and_camera_source_join(self):
        adapter = Adapter()
        receipt = self.run_capture(adapter)
        self.assertFalse(receipt['physical_acceptance_claimed'])
        self.assertAlmostEqual(receipt['observation']['ego_minus_other_upper_entry_s'],.3)
        self.assertEqual(receipt['observation']['other_approach_side_of_ego'],'right')
        manifest = json.loads((self.root/'attempt'/'source-manifest.json').read_text())
        self.assertEqual(manifest['case_id'],self.case)
        index = json.loads((self.root/'attempt'/'original-camera-index.json').read_text())
        self.assertEqual({key:len(value) for key,value in index['channels'].items()},
                         dict.fromkeys(CAMERAS,900))
        receipt = audit(self.root/'attempt', self.survey_path)
        self.assertEqual(receipt['source_integrity'],'passed')
        self.assertEqual(receipt['native_frames'],900)
        self.assertEqual(receipt['camera_frames'],3600)
        self.assertTrue(receipt['all_camera_pixels_decoded'])
        media_path = self.root/'attempt'/index['channels']['front'][0]['source_path']
        media_path.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError,'media digest differs'):
            audit(self.root/'attempt', self.survey_path)
        self.assertTrue(adapter.closed)
        self.assertEqual(adapter.destroyed,[11,10])

    def test_clock_or_camera_failure_closes_owned_resources(self):
        for adapter,error in ((Adapter(drift=True),'clock discontinuity'),
                              (Adapter(missing_camera=True),'camera missing')):
            with self.subTest(error=error):
                output = self.root/'attempt'
                if output.exists():
                    import shutil
                    shutil.rmtree(output)
                with self.assertRaisesRegex(ValueError,error):
                    self.run_capture(adapter)
                self.assertTrue(adapter.closed)
                self.assertEqual(adapter.stopped,[11,10])
                self.assertEqual(adapter.destroyed,[11,10])
                self.assertFalse((output/'source-manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
