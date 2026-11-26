import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from capture_seal import CAMERAS, seal
from parked_lamps import CASES, ROW_SOURCES
from test_source_packet import packet_fixture


def make_stage(folder, case):
    packet_path, packet = packet_fixture(folder, case)
    packet['scene']['park_start_frame'] = 1
    packet_path.write_text(json.dumps(packet) + '\n')
    scene = packet['scene']
    rows = []
    for index in range(3):
        row = {'original_frame': 250 + index, 'time_s': 10 + index / 20,
               'vehicle_id': 'v1', 'night': case.night,
               'lawful_park': case.lawful_park, 'lamp_mode': case.lamp_mode,
               'auxiliary_lamp': case.auxiliary_lamp,
               'speed_mps': 1.0 if index == 0 else 0.0,
               'beam_aim_deg': 2.0 if case.lamp_mode == 'undimmed' else -2.0}
        row.update({name + '_source_sha256': scene[name + '_source_sha256']
                    for name in ROW_SOURCES})
        rows.append(row)
    (folder / 'original-ticks.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    cameras = {}
    for name in CAMERAS:
        frames = []
        for row in rows:
            file = folder / f'{name}-{row["original_frame"]}.png'
            Image.new('RGB', (4, 4), color=(30, 40, 50)).save(file)
            frames.append({'original_frame': row['original_frame'],
                           'time_s': row['time_s'], 'path': file.name,
                           'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        cameras[name] = frames
    (folder / 'camera-source-manifest.json').write_text(json.dumps({
        'source_kind': 'synthetic_fixture', 'cameras': cameras}) + '\n')
    (folder / 'native-owner-release.json').write_text(json.dumps({
        'case_id': packet['case_id'], 'source_kind': 'synthetic_fixture',
        'last_original_frame': 252, 'world_restored': True,
        'owned_actor_ids': ['vehicle'], 'destroyed_actor_ids': ['vehicle']}) + '\n')


class CaptureSealTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.runtime-work' / 'c229398-capture-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_cases_seal_diagnostic_but_refuse_original_claim(self):
        for case in CASES:
            with self.subTest(case=case.name):
                make_stage(self.folder, case)
                receipt = seal(self.folder, diagnostic_fixture=True)
                self.assertEqual(receipt['source_frame_count'], 3)
                self.assertEqual(set(receipt['camera_sources']), set(CAMERAS))
                self.assertFalse(receipt['physical_acceptance_claimed'])
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    seal(self.folder)

    def test_missing_media_and_changed_source_rejected(self):
        make_stage(self.folder, CASES[0])
        (self.folder / 'overview-250.png').unlink()
        with self.assertRaisesRegex(ValueError, 'camera source bytes'):
            seal(self.folder, diagnostic_fixture=True)
        make_stage(self.folder, CASES[0])
        (self.folder / 'beam_aim.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source bytes'):
            seal(self.folder, diagnostic_fixture=True)

    def test_time_join_and_owner_release_rejected(self):
        make_stage(self.folder, CASES[0])
        path = self.folder / 'original-ticks.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['time_s'] += .1
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            seal(self.folder, diagnostic_fixture=True)
        make_stage(self.folder, CASES[0])
        path = self.folder / 'native-owner-release.json'
        release = json.loads(path.read_text())
        release['world_restored'] = False
        path.write_text(json.dumps(release) + '\n')
        with self.assertRaisesRegex(ValueError, 'owner release'):
            seal(self.folder, diagnostic_fixture=True)
