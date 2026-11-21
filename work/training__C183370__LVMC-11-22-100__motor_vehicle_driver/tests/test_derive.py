"""Raw-source channel checks, including a missing-contact and tampered-speed case."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from derive_mandatory_channels import derive


def write_source(root, *, crossing, tamper_speed=False):
    root.mkdir()
    (root / 'live-readback.json').write_text(json.dumps({
        'plan': {'laid_polygon_xy_m': [[0, 0], [2, 0], [2, 2], [0, 2]]}}))
    with (root / 'native-actors.jsonl').open('w') as actors, \
         (root / 'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            x = 1 if crossing and 200 <= index < 400 else 10
            vertices = [[x-0.2, 0.5, 0], [x+0.2, 0.5, 0],
                        [x+0.2, 1.5, 0], [x-0.2, 1.5, 0]]
            actors.write(json.dumps({'frame': index,
                'ego_velocity_xyz_mps': [2, 0, 0],
                'ego_speed_mps': 3 if tamper_speed and index == 300 else 2,
                'ego_body_vertices_xyz_m': vertices}) + '\n')
            frames.write(json.dumps({'carla_frame': index,
                'time_s': round((index+1)/20, 2)}) + '\n')


class DerivedChannelsTest(unittest.TestCase):
    def test_measured_contact_and_speed_from_raw_sources(self):
        with tempfile.TemporaryDirectory(prefix='c183370-raw-') as temp:
            root = Path(temp)
            for crossing, count in ((True, 200), (False, 0)):
                source = root / ('cross' if crossing else 'avoid')
                output = root / ('cross-out' if crossing else 'avoid-out')
                write_source(source, crossing=crossing)
                receipt = derive(source, output)
                contacts = [json.loads(row)['value'] for row in
                            (output / 'newly_laid_footprint_contact.jsonl').read_text().splitlines()]
                speeds = [json.loads(row)['value'] for row in
                          (output / 'ego_speed.jsonl').read_text().splitlines()]
                conditions = [json.loads(row)['value'] for row in
                              (output / 'drive_over_warned_new_pavement.jsonl').read_text().splitlines()]
                self.assertEqual(sum(contacts), count)
                self.assertEqual(set(speeds), {2.0})
                self.assertEqual(sum(item['surveyed_polygon_contact'] for item in conditions), count)
                self.assertTrue(all(item['drive_over_warned_new_pavement'] is None and
                                    item['warning_act_verified'] is False and
                                    item['newly_laid_or_repaired_status_verified'] is False
                                    for item in conditions))
                self.assertFalse(receipt['warning_and_surface_status_verified'])

    def test_reported_speed_cannot_override_retained_velocity(self):
        with tempfile.TemporaryDirectory(prefix='c183370-tamper-') as temp:
            root = Path(temp)
            source = root / 'tamper'
            write_source(source, crossing=True, tamper_speed=True)
            with self.assertRaisesRegex(ValueError, 'speed differs'):
                derive(source, root / 'output')


if __name__ == '__main__':
    unittest.main()
