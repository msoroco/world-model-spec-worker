"""Exercise raw source joins and pass-clearance observations."""

import json
from pathlib import Path
import tempfile
import unittest

from measure import measure


ROOT = Path(__file__).resolve().parent.parent


class MeasureTests(unittest.TestCase):
    def sources(self, folder, name):
        retained = ROOT / 'fixtures' / 'roundabout' / name
        rows = [json.loads(x) for x in (retained / 'actors.jsonl').read_text().splitlines()]
        native = []
        frames = []
        for i, source in enumerate(rows):
            actors = source['actors']
            center = actors['ego']
            actors['ego']['body_vertices_native_m'] = [
                [center['x_m']+dx, center['y_m']+dy, 0]
                for dx,dy in ((-.1,-.1),(-.1,.1),(.1,-.1),(.1,.1))]
            native.append({'native_frame': 1000+i, 'time_s': i/20,
                           'source_kind': 'synthetic_native_sample',
                           'actors': actors,
                           'pass_observation': {'slower_vehicle_ahead': i < 300,
                                                'slower_vehicle_cleared': i >= 300}})
            frames.append({'native_frame': 1000+i, 'video_frame': i, 'time_s': i/20})
        geometry = json.loads((retained / 'geometry.json').read_text())
        geometry.update(source_kind='synthetic_native_sample', center_xy_m=[0,0],
                        same_direction_marked_lanes_source='synthetic annular geometry fixture')
        (folder/'config.json').write_text(json.dumps({'case_id': name, 'frames': 600, 'rate_hz': 20})+'\n')
        (folder/'geometry.json').write_text(json.dumps(geometry)+'\n')
        self.write_rows(folder/'native.jsonl', native)
        self.write_rows(folder/'video_frames.jsonl', frames)
        return native, frames

    @staticmethod
    def write_rows(path, rows):
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def measured(self, folder):
        return measure(folder/'config.json', folder/'native.jsonl',
                       folder/'video_frames.jsonl', folder/'geometry.json')

    def test_lane_and_pass_clearance(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.sources(folder, 'extreme_right')
            observed = self.measured(folder)
            self.assertEqual(observed['counts']['extreme_right'], 600)
            self.assertEqual(observed['first_clearance_frame'], 300)
            self.assertEqual(observed['counts']['after_pass_right'], 300)
            self.assertIsNone(observed['impeding_judgment'])

    def test_missing_follower_and_time_join_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            native, frames = self.sources(folder, 'inner_left')
            native[12]['actors'].pop('follower')
            self.write_rows(folder/'native.jsonl', native)
            with self.assertRaisesRegex(ValueError, 'ego/follower source missing'):
                self.measured(folder)
            native, frames = self.sources(folder, 'inner_left')
            frames[12]['native_frame'] += 1
            self.write_rows(folder/'video_frames.jsonl', frames)
            with self.assertRaisesRegex(ValueError, 'frame-time join differs'):
                self.measured(folder)


if __name__ == '__main__':
    unittest.main()
