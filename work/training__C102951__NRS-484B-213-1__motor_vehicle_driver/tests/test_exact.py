import json
import shutil
import tempfile
import unittest
from pathlib import Path
from runner import CAPTURE_ATOMS, check, lookahead_index

CONFIG = json.loads(Path('config.json').read_text())
DISTANCE = CONFIG['distance_m']
CANDIDATE = CONFIG['candidate_id']

class ExactPassingRequest(unittest.TestCase):
    def test_600_frame_primary_and_four_cameras(self):
        result = check(Path.cwd(), DISTANCE, CANDIDATE)
        self.assertEqual(result['requested_frames'], 600)
        self.assertFalse(result['original_native_observed'])
        self.assertEqual(set(CAPTURE_ATOMS), {'st.sight_distance', 'rel.visible'})

    def test_last_controller_lookahead(self):
        self.assertEqual(lookahead_index(480,600),495)
        self.assertEqual(lookahead_index(599,600),599)

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            for source in Path.cwd().iterdir():
                if source.is_file(): shutil.copy2(source,target/source.name)
            path = target/'config.json'
            data = json.loads(path.read_text())
            data['road_sha256'] = '0'*64
            path.write_text(json.dumps(data)+'\n')
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                check(target,DISTANCE,CANDIDATE)
