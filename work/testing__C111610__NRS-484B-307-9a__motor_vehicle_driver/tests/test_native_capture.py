import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_capture import capture
from saved_turn import audit_saved_attempt
import test_saved_turn


class Adapter:
    def __init__(self, site_raw, image, *, gap=False, camera_gap=False):
        self.site_sha256 = hashlib.sha256(site_raw).hexdigest()
        self.image = image
        self.index = 0
        self.gap = gap
        self.camera_gap = camera_gap

    def source_attestation(self):
        return {"native_origin": True, "site_sha256": self.site_sha256,
                "source_ref": "reviewed Native source fixture"}

    def tick(self):
        i = self.index
        self.index += 1
        frame = 1000 + i + (1 if self.gap and i == 1 else 0)
        row = {"frame": i, "ego_head_id": "ego-head",
               "opposing_head_id": "opp-head", "ego_red": True,
               "opposing_red": True, "ego_arrow_direction": "left",
               "pedestrian_actor_id": 91,
               "pedestrian_permission_source_id": "ped-head",
               "other_traffic_actor_id": 92,
               "other_traffic_lawful_context": True,
               "other_traffic_in_intersection": False,
               "pedestrian_lawful_context": True,
               "pedestrian_xy": [1, 1] if i < 200 else [5, 5],
               "ego_route_lane_id": 2, "ego_in_intersection": i >= 300,
               "ego_speed_mps": 0.0 if i < 200 else 2.0}
        images = {name: {"frame": frame, "png_bytes": self.image}
                  for name in ("front", "left", "right", "rear")}
        if self.camera_gap and i == 1:
            images["rear"]["frame"] += 1
        return {"native_frame": frame, "native_elapsed_s": 100 + i / 20,
                "telemetry": row, "cameras": images}


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_saved_turn.SavedTurnTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tmp.cleanup)
        self.site_path = self.fixture.root / 'site.json'
        self.profile_path = self.fixture.root / 'camera_profile.json'
        self.profile_path.write_text(json.dumps({
            'fps': 20, 'duration_frames': 600,
            'cameras': ['front', 'left', 'right', 'rear']}) + '\n')
        self.image = (self.fixture.root / 'front0.png').read_bytes()

    def test_writer_and_saved_full_decode(self):
        output = self.fixture.root / 'native-attempt'
        ref = capture(Adapter(self.site_path.read_bytes(), self.image),
                      self.site_path, self.profile_path, output,
                      'yield_pedestrian')
        result = audit_saved_attempt(output, ref)
        self.assertEqual(result['original_frames'], 600)
        self.assertEqual(sum(v['frames'] for v in result['decoded_cameras'].values()), 2400)
        self.assertTrue(result['comparison_row']['held_until_clear'])
        self.assertFalse(result['physical_acceptance'])
        manifest = json.loads((output / 'manifest.json').read_text())
        frame_map = json.loads((output / 'frame_map.json').read_text())
        frame_map[300]['native_elapsed_s'] += .1
        path = output / 'frame_map.json'
        path.write_text(json.dumps(frame_map) + '\n')
        manifest['frame_map']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path = output / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest) + '\n')
        changed = {'path': 'manifest.json',
                   'sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, 'Native frame map clock gap'):
            audit_saved_attempt(output, changed)

    def test_writer_rejects_original_gaps(self):
        with self.assertRaisesRegex(ValueError, 'frame identity gap'):
            capture(Adapter(self.site_path.read_bytes(), self.image, gap=True),
                    self.site_path, self.profile_path, self.fixture.root / 'gap',
                    'yield_pedestrian')
        with self.assertRaisesRegex(ValueError, 'camera frame mismatch'):
            capture(Adapter(self.site_path.read_bytes(), self.image, camera_gap=True),
                    self.site_path, self.profile_path, self.fixture.root / 'camera-gap',
                    'yield_pedestrian')
