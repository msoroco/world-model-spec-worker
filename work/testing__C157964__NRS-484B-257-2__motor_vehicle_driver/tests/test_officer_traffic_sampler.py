import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import officer_traffic_sampler as TRAFFIC


class OfficerTrafficSamplerTests(unittest.TestCase):
    def fixtures(self, inside=True):
        x = 0.0 if inside else 15.0
        vertices = [NS(x=x, y=0.0), NS(x=x + 1.0, y=0.0),
                    NS(x=x + 1.0, y=1.0), NS(x=x, y=1.0)]
        other = NS(id=33, get_transform=lambda: NS(),
                   bounding_box=NS(get_world_vertices=lambda transform: vertices))
        site = {'format': 'worker-officer-subsection-2-source-intake',
                'site_id': 'CPU-fixture-site',
                'intersection_polygon_xy_m': [[-5, -5], [5, -5], [5, 5], [-5, 5]]}
        hazard = lambda frame: {'site_id': 'CPU-fixture-site',
                                'other_actor_id': 33, 'approaching_hazard': False,
                                'source': f'hazard-review.json#frame-{frame}'}
        return other, site, hazard

    def test_native_body_occupancy_preserves_hazard_uncertainty(self):
        other, site, hazard = self.fixtures()
        inside = TRAFFIC.native_sampler(other, site, hazard)(2)
        self.assertTrue(inside['other_inside'])
        self.assertEqual(inside['other_actor_id'], 33)
        self.assertEqual(inside['legal_immediate_hazard_judgment'], 'unresolved')
        outside_actor, _, _ = self.fixtures(inside=False)
        self.assertFalse(TRAFFIC.native_sampler(outside_actor, site, hazard)(2)['other_inside'])

    def test_missing_body_or_hazard_source_rejected(self):
        other, site, hazard = self.fixtures()
        other.bounding_box.get_world_vertices = lambda transform: [NS(x=0.0, y=0.0)]
        with self.assertRaisesRegex(ValueError, 'Complete Native other vehicle body'):
            TRAFFIC.native_sampler(other, site, hazard)(0)
        other, site, hazard = self.fixtures()
        with self.assertRaisesRegex(ValueError, 'Sourced approaching-hazard judgment'):
            TRAFFIC.native_sampler(other, site, lambda frame: {
                'site_id': 'CPU-fixture-site', 'other_actor_id': 33,
                'approaching_hazard': False, 'source': ''})(0)
        with self.assertRaisesRegex(ValueError, 'Reviewed site intake'):
            TRAFFIC.native_sampler(other, {}, hazard)


if __name__ == '__main__':
    unittest.main()
