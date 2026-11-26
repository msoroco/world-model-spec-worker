"""Source-shaped CPU checks for an unlabeled orientation sweep."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / 'runtime'))
from controlled_orientation_sweep import ANGLE_REQUESTS, build, expand_canonical_plan, measure_original, sha, target
from test_bind_reviewed_site import pair


class ControlledOrientationSweepTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.runtime-work' / 'c150041-orientation-sweep-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        temp = TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.packets = pair(self.root)
        self.packet = self.packets['park']

    def test_full_source_bound_grid_and_no_legal_labels(self):
        output = self.root / 'sweep.json'
        result = build(self.packet, self.packet.parent, output)
        self.assertEqual(result['engineering_angles_deg'], list(ANGLE_REQUESTS))
        self.assertEqual(len(result['constructions']), 10)
        self.assertEqual({r['pose']['orientation_request_deg'] for r in result['constructions']}, set(ANGLE_REQUESTS))
        self.assertTrue(all(r['scene']['case_id'].endswith(f'orientation_sweep-{i:04d}')
                            for i, r in enumerate(result['constructions'])))
        self.assertTrue(all(r['pose']['legal_judgment'] == 'unresolved' and
                            not r['pose']['physical_realization_claimed'] for r in result['constructions']))
        self.assertEqual(json.loads(output.read_text()), json.loads(json.dumps(result)))

    def test_changed_original_and_missing_packet_rejected(self):
        source = self.packet.parent / 'reviewed_sources/activity.txt'
        source.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            build(self.packet, self.packet.parent, self.root / 'bad.json')
        with self.assertRaises(FileNotFoundError):
            build(self.root / 'missing.json', self.packet.parent, self.root / 'missing-output.json')

    def test_unfrozen_angle_and_infeasible_footprint_rejected(self):
        from parking_site_acquisition import validate
        context = validate(self.packet, source_root=self.packet.parent)
        with self.assertRaisesRegex(ValueError, 'frozen engineering sweep point'):
            target(context, 11)
        with self.assertRaisesRegex(ValueError, 'footprint leaves'):
            target(context, 90, length_m=300)

    def test_saved_body_measurement_and_missing_history_rejected(self):
        from parking_site_acquisition import validate
        context = validate(self.packet, source_root=self.packet.parent)
        pose = target(context, 30)
        history = self.root / 'history.jsonl'
        rows = [{'frame': i, 'time_s': i / 20,
                 'body_vertices_xy_m': pose['target_body_vertices_xy_m'],
                 'vehicle_forward_xy': pose['target_forward_xy']}
                for i in range(3)]
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        measured = measure_original(self.packet, self.packet.parent, history, sha(history))
        self.assertEqual(len(measured['observations']), 3)
        self.assertAlmostEqual(measured['observations'][-1]['parallel_deviation_deg'], 30)
        self.assertEqual(measured['legal_judgment'], 'unresolved')
        with self.assertRaisesRegex(ValueError, 'history hash changed'):
            measure_original(self.packet, self.packet.parent, history, '0' * 64)
        history.unlink()
        with self.assertRaises(FileNotFoundError):
            measure_original(self.packet, self.packet.parent, history, '0' * 64)

    def test_pinned_canonical_expansion_is_ten_unlabeled_points(self):
        proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
        expanded = expand_canonical_plan(proposal)
        sweep = [case for case in expanded['cases'] if case['target_type'] == 'judgment_sweep']
        self.assertEqual(len(sweep), 10)
        self.assertTrue(expanded['sweeps_expanded'])
        self.assertTrue(all(case['unresolved_judgment_calls'] for case in sweep))
        self.assertEqual({case['sweep_point']['orientation_request_deg'] for case in sweep},
                         set(ANGLE_REQUESTS))

    def test_stand_activity_uses_separate_source_packet(self):
        packet = self.packets['stand']
        result = build(packet, packet.parent, self.root / 'stand-sweep.json', activity='stand')
        self.assertEqual(len(result['constructions']), 10)
        self.assertTrue(all(row['pose']['activity_request'] == 'stand'
                            for row in result['constructions']))
        self.assertNotEqual(result['site_packet_sha256'],
                            build(self.packet, self.packet.parent, self.root / 'park-sweep.json')['site_packet_sha256'])
