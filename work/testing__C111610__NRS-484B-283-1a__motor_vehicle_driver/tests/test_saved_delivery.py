import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from native_capture import capture
from saved_delivery import join
from test_native_capture import Adapter, SCENE, packet


class SavedDeliveryTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'c111610-saved-delivery-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.site = self.root / 'site.json'
        self.site.write_text(json.dumps(packet()) + '\n', encoding='utf-8')
        self.exception = self.root / 'exception.json'
        self.exception.write_text(json.dumps({
            'case_id': json.loads(SCENE.read_text())['case_id'],
            'status': 'none_identified',
            'source_refs': ['fixture/exception-review.json']}) + '\n', encoding='utf-8')
        self.dims = {name: (2, 2) for name in
                     ('overview', 'approach', 'reference_corner', 'driver_reference')}
        self.attempt = self.root / 'attempt'
        capture(Adapter(self.site.read_bytes()), SCENE, self.site, self.exception,
                self.attempt, dimensions=self.dims)

    def test_join_seals_original_actor_and_camera_clocks(self):
        receipt = join(self.attempt, SCENE, self.root / 'delivery.json', dimensions=self.dims)
        self.assertEqual(receipt['joined_frames'], 600)
        self.assertEqual(receipt['decoded_view_frames'], 2400)
        self.assertEqual(receipt['actor_camera_clock_join'], 'verified')
        self.assertFalse(receipt['physical_source_verified'])

    def test_resealed_actor_native_clock_drift_is_rejected(self):
        ego_path = self.attempt / 'ego.json'
        ego = json.loads(ego_path.read_text())
        ego[235]['native_frame'] += 1
        ego_path.write_text(json.dumps(ego) + '\n', encoding='utf-8')
        index_path = self.attempt / 'source-index.json'
        index = json.loads(index_path.read_text())
        index['files']['ego']['sha256'] = hashlib.sha256(ego_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'actor/camera frame-time join mismatch'):
            join(self.attempt, SCENE, self.root / 'delivery.json', dimensions=self.dims)


if __name__ == '__main__':
    unittest.main()
