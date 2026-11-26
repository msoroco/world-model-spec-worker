import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake import CASES
from runner import VIEWS, load_scene, run
from analysis import build, compare
from audit import audit_delivery
from test_overtake import Adapter, rows, scene

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT.name


class CaptureAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.frame = 100
        self.recorded = []
        self.road = b''

    def map_opendrive_bytes(self):
        return self.road

    def pass_route_readback(self, cycle, motor):
        return True

    def begin_four_camera_capture(self, views, cameras, owned, output):
        self.events.append(('capture', tuple(views)))

    def tick(self):
        value = self.frame
        self.frame += 1
        return value

    def record_original_pass_readback(self, frame, built, output):
        self.recorded.append(frame)

    def finish_four_camera_capture(self, output):
        self.events.append(('capture_done',))
        root = Path(output)
        for name in ('pass-readback.jsonl', 'trace.jsonl', 'video_frames.jsonl'):
            (root / name).write_text('test fixture only\n')
        for name in VIEWS:
            (root / (name + '.mkv')).write_bytes(b'test fixture only')

    def camera_frame_counts(self):
        return {name: 900 for name in VIEWS}

    def native_source_kind(self):
        return 'original_native_capture'


def write_packet(root, case):
    x = scene(case)
    sources = {}
    for field in ('jurisdiction', 'road_geometry', 'cycle_classification',
                  'wheel_arrangement', 'wheel_diameter', 'moped_exclusion',
                  'operator_control', 'motor_vehicle_classification',
                  'motor_vehicle_occupants', 'passing_side', 'route_geometry'):
        name = field + '.txt'
        target = root / name
        target.write_text('reviewed fixture ' + field)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        x[field + '_source_sha256'] = digest
        sources[field] = {'path': name, 'sha256': digest}
    packet = root / 'packet.json'
    packet.write_text(json.dumps({'case_id': ASSIGNMENT + '__' + case.case_id,
                                  'source_kind': 'reviewed_original_scene',
                                  'scene': x, 'sources': sources}))
    return packet, x


class CaptureAndSavedTest(unittest.TestCase):
    def test_all_selected_runner_call_paths(self):
        for case in CASES:
            with self.subTest(case=case.case_id), tempfile.TemporaryDirectory(
                    dir=Path.cwd() / '.runtime-work') as tmp:
                root = Path(tmp)
                packet, x = write_packet(root, case)
                loaded, digest = load_scene(packet, root, case)
                self.assertEqual(loaded, x)
                config_path = ROOT / ('config.json' if case == CASES[0] else
                                      'cases/' + case.case_id + '/config.json')
                config = json.loads(config_path.read_text())
                (root / 'config.json').write_text(json.dumps(config))
                adapter = CaptureAdapter()
                adapter.road = (root / 'road_geometry.txt').read_bytes()
                result = run(adapter, loaded, case, config, root, digest)
                self.assertEqual(result['frame_count'], 900)
                self.assertTrue((root / 'original-sources.json').is_file())
                self.assertFalse(result['physical_acceptance_claimed'])
                self.assertEqual(len(adapter.recorded), 900)
                self.assertEqual(adapter.events[-2:],
                                 [('destroy', 'motor'), ('destroy', 'cycle')])

    def test_missing_and_modified_original_source_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as tmp:
            root = Path(tmp)
            packet, _ = write_packet(root, CASES[0])
            (root / 'road_geometry.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                load_scene(packet, root, CASES[0])
            (root / 'road_geometry.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'source file missing'):
                load_scene(packet, root, CASES[0])

    def test_live_road_mismatch_rejected_before_actor_creation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as tmp:
            root = Path(tmp)
            packet, _ = write_packet(root, CASES[0])
            loaded, digest = load_scene(packet, root, CASES[0])
            config = json.loads((ROOT / 'config.json').read_text())
            adapter = CaptureAdapter()
            adapter.road = b'wrong live map'
            with self.assertRaisesRegex(ValueError, 'live road geometry differs'):
                run(adapter, loaded, CASES[0], config, root, digest)
            self.assertFalse(adapter.events)

    def test_upstream_fallback_requires_reviewed_source(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as tmp:
            root = Path(tmp)
            packet, _ = write_packet(root, CASES[0])
            with self.assertRaisesRegex(ValueError, 'upstream fallback approval'):
                load_scene(packet, root, CASES[0], 1)
            doc = json.loads(packet.read_text())
            approved = root / 'upstream_start.txt'
            approved.write_text('one meter upstream reviewed fixture')
            digest = hashlib.sha256(approved.read_bytes()).hexdigest()
            doc['sources']['upstream_start'] = {'path': approved.name,
                                                 'sha256': digest}
            doc['scene']['upstream_start_source_sha256'] = digest
            doc['scene']['approved_upstream_start_m'] = 1
            packet.write_text(json.dumps(doc))
            loaded, packet_hash = load_scene(packet, root, CASES[0], 1)
            config = json.loads((ROOT / 'config.json').read_text())
            config['cycle_start_offset_m'] = 1
            (root / 'config.json').write_text(json.dumps(config))
            adapter = CaptureAdapter()
            adapter.road = (root / 'road_geometry.txt').read_bytes()
            result = run(adapter, loaded, CASES[0], config, root, packet_hash)
            self.assertEqual(result['frame_count'], 900)
            self.assertTrue(any(item[0] == 'pass_route' for item in adapter.events))

    def test_saved_rejects_missing_manifest_and_claims(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'sealed original source'):
                build(root)
            (root / 'original-sources.json').write_text(json.dumps({
                'source_kind': 'synthetic_diagnostic_fixture',
                'accepted_original_source': False}))
            with self.assertRaisesRegex(ValueError, 'original Native capture'):
                build(root)
            with self.assertRaisesRegex(ValueError, 'original Native capture'):
                audit_delivery(root, root / 'analysis-report.json')

    def test_comparison_requires_source_bound_distinct_cases(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        comparison = plan['comparisons'][0]
        a = {'format': 'worker-analysis-report',
             'case_id': comparison['case_ids'][0],
             'measurements': {'cycle_motor_pass': {'value': {
                 'frame_count': 900, 'other_occupant_ids': ['driver'],
                 'road_geometry_source_sha256': 'road', 'cycle_kind': 'bicycle',
                 'pass_policy': 'complete', 'requested_lateral_offset_m': 2.5},
                 'sources': {'pass-readback.jsonl': 'a'}}}}
        b = json.loads(json.dumps(a))
        b['case_id'] = comparison['case_ids'][1]
        b['measurements']['cycle_motor_pass']['value']['requested_lateral_offset_m'] = 1.5
        self.assertFalse(compare(a, b, comparison)['legal_verdict_claimed'])
        b['measurements']['cycle_motor_pass']['sources'] = {}
        with self.assertRaisesRegex(ValueError, 'source-bound'):
            compare(a, b, comparison)

    def test_all_four_controlled_comparison_rules(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        settings = {ASSIGNMENT + '__' + case.case_id: case for case in CASES}

        def report(case_id):
            case = settings[case_id]
            return {'format': 'worker-analysis-report', 'case_id': case_id,
                    'measurements': {'cycle_motor_pass': {
                        'value': {'frame_count': 900,
                                  'other_occupant_ids': ['driver', 'passenger'],
                                  'road_geometry_source_sha256': 'road',
                                  'cycle_kind': case.cycle_kind,
                                  'requested_lateral_offset_m': case.lateral_offset_m,
                                  'pass_policy': case.pass_policy},
                        'sources': {'pass-readback.jsonl': case.case_id}}}}

        for comparison in plan['comparisons']:
            with self.subTest(comparison=comparison['comparison_id']):
                a, b = [report(cid) for cid in comparison['case_ids']]
                self.assertFalse(compare(a, b, comparison)[
                    'physical_acceptance_claimed'])
                b['measurements']['cycle_motor_pass']['value'][
                    'road_geometry_source_sha256'] = 'different road'
                with self.assertRaisesRegex(ValueError, 'fixed frame or occupant'):
                    compare(a, b, comparison)


if __name__ == '__main__':
    unittest.main()
