"""Synthetic source-shape tests only; these are not physical receipts."""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_audit import audit_case, audit_comparison
from pass_right_route import build_case
from test_pass_right_route import map_packet
from test_pass_right_measure import trace


def sealed(root, name, data):
    path = root / name
    path.write_text(json.dumps(data))
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def attempt(root, variant):
    packet = map_packet()
    manifest = {
        'assignment_id': 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver',
        'case_id': 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver__' + variant,
        'variant': variant, 'diagnostic_fixture': False,
        'map': sealed(root, 'map.json', packet),
        'trace': sealed(root, 'trace.json', trace({'left_signal': 'signal', 'left_turn': 'turn', 'neither': 'none'}[variant])),
        'route_request': sealed(root, 'route.json', build_case(packet, variant)),
        'frame_count': 12,
        'cameras': {name: sealed(root, name + '.json', {'camera': name})
                    for name in ('front', 'rear', 'left', 'right')},
    }
    return manifest


class TestSavedSourceAudit(unittest.TestCase):
    def test_case_and_both_comparisons_from_reopened_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp) / name for name in ('signal', 'turn', 'neither')]
            for root in roots:
                root.mkdir()
            audits = [audit_case(root, attempt(root, variant)) for root, variant in
                      zip(roots, ('left_signal', 'left_turn', 'neither'))]
            self.assertEqual(audit_comparison(audits[0], audits[2], 'left_signal_presence')['observed_difference'],
                             'target_left_signal_during_pass')
            self.assertEqual(audit_comparison(audits[1], audits[2], 'left_turn_motion_presence')['observed_difference'],
                             'target_left_motion_during_pass')
            self.assertFalse(any(a['physical_acceptance_claimed'] for a in audits))

    def test_rejects_missing_and_tampered_original_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = attempt(root, 'left_signal')
            (root / 'trace.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'sha256 mismatch'):
                audit_case(root, manifest)
            manifest = attempt(root, 'left_signal')
            (root / 'right.json').unlink()
            with self.assertRaisesRegex(ValueError, 'outside saved attempt or missing'):
                audit_case(root, manifest)

    def test_rejects_route_request_and_wrong_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = attempt(root, 'left_turn')
            manifest['route_request'] = sealed(root, 'route.json', build_case(map_packet(), 'neither'))
            with self.assertRaisesRegex(ValueError, 'route request differs'):
                audit_case(root, manifest)
            manifest = attempt(root, 'left_turn'); manifest['case_id'] += '_wrong'
            with self.assertRaisesRegex(ValueError, 'exact case identity'):
                audit_case(root, manifest)

    def test_rejects_diagnostic_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = attempt(root, 'neither')
            manifest['diagnostic_fixture'] = True
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                audit_case(root, manifest)
            manifest['diagnostic_fixture'] = False
            manifest['map']['path'] = '../outside.json'
            with self.assertRaisesRegex(ValueError, 'outside saved attempt'):
                audit_case(root, manifest)

    def test_rejects_fixed_condition_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            aroot = Path(tmp) / 'a'; broot = Path(tmp) / 'b'; aroot.mkdir(); broot.mkdir()
            a = audit_case(aroot, attempt(aroot, 'left_signal'))
            b = audit_case(broot, attempt(broot, 'neither'))
            b = copy.deepcopy(b); b['initial_target_speed_mps'] += 1
            with self.assertRaisesRegex(ValueError, 'fixed comparison condition differs'):
                audit_comparison(a, b, 'left_signal_presence')
            with self.assertRaisesRegex(ValueError, 'exact comparison case pair'):
                audit_comparison(a, a, 'left_signal_presence')


if __name__ == '__main__':
    unittest.main()
