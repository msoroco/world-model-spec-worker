"""Numerical long-duration checks; generated samples are never Native proof."""
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from geometry import body, ego_y, other_x
from measure import joined_samples, measure_arrow_and_yield


def samples(yield_to_other=True):
    result = []
    for frame in range(840):
        other_body = body(other_x(frame), -1.75, 'east')
        within = any(-7 < vertex[0] < 7 for vertex in other_body) and frame < 169
        result.append({
            'native_frame': frame,
            'native_body_xy_m': body(1.75, ego_y(frame, yield_to_other), 'north'),
            'native_yaw_deg': 90.0, 'speed_mps': 0.0 if yield_to_other and 100 <= frame < 169 else 4.0,
            'governing_signal': {
                'native_actor_id': 22, 'native_state': 'Red' if frame < 100 else 'Green',
                'authored_aspect': 'green_straight_arrow', 'facing_ego_native_survey': True,
                'pixel_aspect_verified': frame >= 100},
            'other_vehicle': {
                'native_actor_id': 23, 'native_body_xy_m': other_body,
                'within_intersection_or_adjacent_crosswalk': within},
        })
    return result


class MeasureStraightArrow(unittest.TestCase):
    def test_42_second_yield_and_non_yield(self):
        safe = measure_arrow_and_yield(samples(True), verified_arrow_frames=set(range(100, 840)))
        unsafe = measure_arrow_and_yield(samples(False), verified_arrow_frames=set(range(100, 840)))
        self.assertEqual(safe['sole_arrow_pixel_verified_frames'], 740)
        self.assertTrue(safe['yielded_before_entry'])
        self.assertFalse(unsafe['yielded_before_entry'])
        self.assertTrue(safe['straight_heading_no_turn_observed'])
        self.assertFalse(safe['other_vehicle_lawful_entry_inferred'])

    def test_missing_pixel_aspect_fails_closed(self):
        source = samples(True)
        with self.assertRaisesRegex(ValueError, 'No verified sole'):
            measure_arrow_and_yield(source)

    def test_gradual_turn_is_detected(self):
        source = samples(True)
        for frame in range(300, 360):
            source[frame]['native_yaw_deg'] = 90 + (frame - 300) / 2
        result = measure_arrow_and_yield(source, verified_arrow_frames=set(range(100, 840)))
        self.assertFalse(result['straight_heading_no_turn_observed'])

    def test_original_frame_body_and_capture_join_rejects_mismatch(self):
        with TemporaryDirectory() as directory:
            attempt = Path(directory)
            (attempt / 'capture').mkdir()
            footprints = [body(1.75, -17 + index, 'north') for index in range(2)]
            sources = {
                'native_samples.jsonl': [
                    {'native_frame': 100 + i, 'time_s': (i + 1) / 2,
                     'native_body_xy_m': feet} for i, feet in enumerate(footprints)],
                'body_history.jsonl': [
                    {'frame': 100 + i, 'time_s': (i + 1) / 2,
                     'body_vertices_m': feet} for i, feet in enumerate(footprints)],
                'video_frames.jsonl': [
                    {'video_frame': i, 'native_frame': 100 + i,
                     'time_s': (i + 1) / 2} for i in range(2)],
                'trace.jsonl': [
                    {'frame': 100 + i, 'time_s': (i + 1) / 2} for i in range(2)],
                'capture/evidence.jsonl': [
                    {'original_frame': 100 + i, 'recording_time_s': (i + 1) / 2,
                     'ego': {'body_vertices_m': feet}} for i, feet in enumerate(footprints)],
            }
            for name, rows in sources.items():
                (attempt / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
            joined, audit = joined_samples(attempt, rate_hz=2, duration_s=1)
            self.assertEqual((len(joined), audit['frames']), (2, 2))
            sources['video_frames.jsonl'][1]['native_frame'] = 104
            (attempt / 'video_frames.jsonl').write_text(''.join(
                json.dumps(row) + '\n' for row in sources['video_frames.jsonl']))
            with self.assertRaisesRegex(ValueError, 'video frame mapping'):
                joined_samples(attempt, rate_hz=2, duration_s=1)


if __name__ == '__main__':
    unittest.main()
