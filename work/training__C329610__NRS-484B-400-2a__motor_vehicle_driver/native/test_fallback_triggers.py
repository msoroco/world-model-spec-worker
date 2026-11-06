"""Synthetic source-bound fallback tests; no original pixel observations."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fallback_triggers import evaluate
from pixel_visibility import measure


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


def sealed_route(samples, geometry, **changes):
    route = {'source_kind': 'native_map_readback', 'connected_lane_link': True,
             'full_body_destination_exit_observed_by_24s': True,
             'native_samples_sha256': hashlib.sha256(samples.read_bytes()).hexdigest(),
             'road_geometry_sha256': hashlib.sha256(geometry.read_bytes()).hexdigest(),
             'native_map_sha256': '0' * 64}
    route.update(changes)
    return route


class TriggerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        self.samples = folder/'native_samples.jsonl'
        self.geometry = folder/'road_geometry.json'
        self.route = folder/'route_audit.json'
        self.pixels = folder/'pixel_audit.json'
        self.mapping = folder/'video_frames.jsonl'
        self.video = folder/'approach.mkv'
        self.review = folder/'pixel_review.jsonl'
        write(self.samples, {'native_center_xy_m': [-20, -1.75], 'native_frame': 100, 'time_s': .05})
        write(self.geometry, {'native_map_sha256': '0' * 64})
        write(self.route, sealed_route(self.samples, self.geometry))
        write(self.mapping, {'video_frame': 0, 'native_frame': 100, 'time_s': .05})
        self.video.write_bytes(b'synthetic camera source; not decoded')
        self.mark(True)

    def mark(self, visible):
        write(self.review, {'video_frame': 0, 'native_frame': 100,
                            'body_visible': visible, 'centerline_visible': True})
        write(self.pixels, measure(self.samples, self.mapping, self.video, self.review))

    def trigger(self):
        return evaluate(self.samples, self.geometry, self.route, self.pixels, -1.75)

    def test_thresholds_and_independent_failures(self):
        self.assertEqual([self.trigger()[key] for key in ('fallback1','fallback2','fallback3')],
                         [False, False, False])
        write(self.route, sealed_route(self.samples, self.geometry, connected_lane_link=False))
        self.assertTrue(self.trigger()['fallback1'])
        write(self.route, sealed_route(self.samples, self.geometry))
        write(self.samples, {'native_center_xy_m': [-20, -2.11], 'native_frame': 100, 'time_s': .05})
        write(self.route, sealed_route(self.samples, self.geometry))
        self.mark(True)
        self.assertTrue(self.trigger()['fallback2'])
        write(self.samples, {'native_center_xy_m': [-20, -1.75], 'native_frame': 100, 'time_s': .05})
        write(self.route, sealed_route(self.samples, self.geometry))
        self.mark(False)
        self.assertTrue(self.trigger()['fallback3'])

    def test_unobserved_source_rejected(self):
        write(self.route, sealed_route(self.samples, self.geometry, source_kind='authored_request'))
        with self.assertRaisesRegex(ValueError, 'original-source'):
            self.trigger()

    def test_changed_sources_reject(self):
        write(self.samples, {'native_center_xy_m': [-20, -2.0], 'native_frame': 100, 'time_s': .05})
        with self.assertRaisesRegex(ValueError, 'source or count mismatch'):
            self.trigger()
        write(self.samples, {'native_center_xy_m': [-20, -1.75], 'native_frame': 100, 'time_s': .05})
        write(self.geometry, {'native_map_sha256': '1' * 64})
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.trigger()


if __name__ == '__main__':
    unittest.main()
