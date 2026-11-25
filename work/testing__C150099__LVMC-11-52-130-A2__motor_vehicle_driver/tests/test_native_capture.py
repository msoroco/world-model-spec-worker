import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, capture
from source_packet import SOURCES, validate_packet
from saved_audit import audit_planned_case
from delivery_audit import audit_capture

PNG = b'\x89PNG\r\n\x1a\n' + b'diagnostic-pixel-source'


class FakeNative:
    native_attested = False
    def __init__(self, map_bytes, fail_frame=None):
        self.map_bytes = map_bytes
        self.frame = 0
        self.fail_frame = fail_frame
        self.cleaned = False
        self.braked = False
        self.control_profile = None
    def get_opendrive_bytes(self): return self.map_bytes
    def ego_body_length_m(self): return 4.0
    def spawn_sign(self, *args): return 'sign'
    def read_sign(self, sign):
        return {'identity_sha256': self.identity_sha,
                'appearance_sha256': self.appearance_sha,
                'physically_present': True, 'text': 'FIRE LANE'}
    def spawn_vehicle(self, *args): return 'ego'
    def set_route(self, *args, **kwargs): pass
    def set_curb_target(self, *args, **kwargs): pass
    def set_control_profile(self, ego, profile):
        self.control_profile = (ego, profile)
    def set_attendance(self, *args): pass
    def tick(self):
        if self.frame == self.fail_frame:
            raise ValueError('synthetic Native tick failure')
        row = {'frame': self.frame, 'time_s': self.frame / 20}
        self.frame += 1
        return row
    def read_footprint(self, frame):
        return {'frame': frame, 'time_s': frame / 20, 'west_x_m': 11,
                'east_x_m': 15, 'curb_gap_m': .2}
    def read_activity(self, frame):
        return {'frame': frame, 'time_s': frame / 20, 'state': 'parked',
                'attended': True, 'exception_kind': 'none'}
    def read_cameras(self, frame):
        return {name: {'frame': frame, 'time_s': frame / 20, 'png': PNG}
                for name in CAMERAS}
    def brake(self): self.braked = True
    def cleanup(self): self.cleaned = True
    def destroy(self, actor): pass


class NativeCaptureTests(unittest.TestCase):
    def packet(self, root):
        case_id = ROOT.name + '__public_park_attended'
        sources = {}
        map_bytes = b'<OpenDRIVE diagnostic="true"/>'
        for name in SOURCES:
            path = root / (name + '.txt')
            path.write_bytes(map_bytes if name == 'map' else (name + '\n').encode())
            sources[name] = {'path': path.name,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            if name in ('fire_code_designation', 'posting_authority', 'jurisdiction'):
                sources[name].update(reviewer='diagnostic', citation='diagnostic')
        packet = {'case_id': case_id, 'source_kind': 'reviewed_original_site',
                  'reviewer': 'diagnostic', 'sign_prop_provenance': 'diagnostic',
                  'sources': sources,
                  'site': {'cell_id': 'C150099', 'layout': 'one_way_road',
                           'property_kind': 'public', 'sign_support': 'spawned_prop',
                           'sign_text': 'FIRE LANE', 'posted_interval_m': [10, 30],
                           'curb_y_m': 2, 'approach_waypoints': [[0, 0], [20, 0]]}}
        path = root / 'packet.json'
        path.write_text(json.dumps(packet) + '\n')
        adapter = FakeNative(map_bytes)
        adapter.identity_sha = sources['sign_identity']['sha256']
        adapter.appearance_sha = sources['sign_appearance']['sha256']
        return path, adapter, case_id

    def test_full_diagnostic_frame_join_and_cleanup(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            packet, adapter, case_id = self.packet(root)
            destination = root / 'attempt'
            inventory = capture(adapter, case_id, packet, destination)
            self.assertTrue(adapter.braked and adapter.cleaned)
            self.assertTrue(inventory['diagnostic_fixture'])
            self.assertEqual(set(inventory['camera_media']), set(CAMERAS))
            copied_packet = destination / 'reviewed-packet.json'
            self.assertEqual(hashlib.sha256(copied_packet.read_bytes()).hexdigest(),
                             inventory['site_sha256'])
            self.assertEqual(validate_packet(copied_packet, case_id),
                             json.loads((destination / 'site.json').read_text()))
            audited = audit_capture(destination, case_id, allow_diagnostic=True)
            self.assertEqual(audited['original_frames'], 900)
            with self.assertRaisesRegex(ValueError, 'synthetic capture'):
                audit_capture(destination, case_id)
            (destination / 'source-review/posting_authority.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'original source hash changed'):
                validate_packet(copied_packet, case_id)
            with self.assertRaisesRegex(ValueError, 'original source hash changed'):
                audit_capture(destination, case_id, allow_diagnostic=True)
            audit = audit_planned_case(destination / 'history.jsonl',
                                       inventory['history_sha256'], case_id,
                                       inventory['site_sha256'])
            self.assertEqual(audit['frame_count'], 900)
            self.assertEqual(audit['observed']['hold_overlap_frames'], 100)

    def test_failed_native_tick_removes_partial_attempt(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            packet, adapter, case_id = self.packet(root)
            adapter.fail_frame = 10
            with self.assertRaisesRegex(ValueError, 'tick failure'):
                capture(adapter, case_id, packet, root / 'attempt')
            self.assertTrue(adapter.braked and adapter.cleaned)
            self.assertFalse((root / 'attempt').exists())

    def test_fallback_applies_distinct_control_before_original_ticks(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            packet, adapter, case_id = self.packet(root)
            inventory = capture(adapter, case_id, packet, root / 'attempt',
                                control_profile='slow_approach')
            self.assertEqual(adapter.control_profile, ('ego', 'slow_approach'))
            self.assertEqual(inventory['control_profile'], 'slow_approach')
            self.assertEqual(audit_capture(root / 'attempt', case_id,
                                           allow_diagnostic=True)['original_frames'], 900)


if __name__ == '__main__':
    unittest.main()
