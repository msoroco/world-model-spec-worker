"""Original-source joins and missing-ray controls for the 407 branch."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_407_measurement import measure_407_visibility


def packet():
    approaches = []
    for lane in (-1, 1):
        rays = [{'clear': i == 0} for i in range(9)]
        approaches.append({'lane_id': lane, 'direction_sign': 1 if lane > 0 else -1,
                           'body_rays_at_probe': rays,
                           'any_sample_clear_at_probe': True,
                           'any_body_sight_horizon': {'bound': 'first_sampled_occlusion',
                                                      'distance_m': 160.0}})
    return {'method': 'actual_actor_body_raycast_v2', 'probe_distance_m': 152.4,
            'required_lane_ids': [-1, 1],
            'visibility_criterion': 'any_of_nine_body_samples', 'approaches': approaches}


def measure(visibility, *, frame=100):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root/'capture.jsonl').write_text(json.dumps({'original_frame': frame,
             'recording_time_s': 0.05, 'visibility': visibility})+'\n')
        (root/'motion.jsonl').write_text(json.dumps({'frame': 100, 'time_s': 0.05})+'\n')
        (root/'context.json').write_text(json.dumps({'approach_lane_id': -1,
                                                      'opposite_lane_id': 1}))
        return measure_407_visibility(root/'capture.jsonl', root/'motion.jsonl', root/'context.json')


class VisibilityTests(unittest.TestCase):
    def test_both_nine_ray_approaches_retained_without_legal_claim(self):
        result = measure(packet())
        self.assertEqual(result['frame_count'], 1)
        self.assertIsNone(result['legal_visibility_judgment'])
        self.assertEqual(set(result['observations'][0]['approaches']), {'-1', '1'})

    def test_missing_direction_or_centre_only_rejected(self):
        for mutation in ('missing_direction', 'centre_only'):
            source = packet()
            if mutation == 'missing_direction':
                source['approaches'].pop()
                expected = 'Both original 407 approach directions required'
            else:
                source['approaches'][0]['body_rays_at_probe'] = [{'clear': True}]
                expected = 'Incomplete 407 nine-body-ray probe'
            with self.assertRaisesRegex(ValueError, expected):
                measure(source)

    def test_route_limited_or_summary_tampered_rejected(self):
        source = packet()
        source['approaches'][1]['any_body_sight_horizon']['bound'] = 'route_limit'
        with self.assertRaisesRegex(ValueError, 'route-limited'):
            measure(source)
        source = packet()
        source['approaches'][0]['any_sample_clear_at_probe'] = False
        with self.assertRaisesRegex(ValueError, 'summary differs'):
            measure(source)

    def test_original_frame_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'frame join differs'):
            measure(packet(), frame=101)

    def test_extra_inventoried_lane_is_validated(self):
        source = packet()
        extra = dict(source['approaches'][0], lane_id=-2)
        source['required_lane_ids'].append(-2)
        source['approaches'].append(extra)
        result = measure(source)
        self.assertEqual(set(result['observations'][0]['approaches']), {'-2', '-1', '1'})
        source['approaches'][-1]['direction_sign'] = 1
        with self.assertRaisesRegex(ValueError, 'direction differs'):
            measure(source)


if __name__ == '__main__':
    unittest.main()
