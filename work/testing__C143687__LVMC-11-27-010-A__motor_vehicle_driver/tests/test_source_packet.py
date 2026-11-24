import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_trail import site_for, trail


MODULE = Path(__file__).resolve().parents[1] / 'source_packet.py'
spec = importlib.util.spec_from_file_location('trail_source_packet', MODULE)
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def fixture(root, case):
    site = site_for(case)
    sources = {}
    for key in packet_module.RECORDS:
        raw = ('original-source-' + key + '-' + case.name).encode()
        path = root / (key + '.txt')
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        sources[key] = {'path': path.name, 'sha256': digest}
        parts = packet_module.RECORDS[key]
        target = site
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = digest
    packet = {
        'cell_id': 'C143687', 'layout': 'nonmotorized_trail',
        'sources': sources,
        'assertions': {
            'official_plan_designation': case.designated,
            'city_trail_dedication': case.dedicated,
            'sign_face_text': site['sign']['face_text'],
            'prohibits_motor_vehicles': case.prohibition_posted,
            'emergency_use': case.emergency_use,
            'maintenance_use': case.maintenance_use,
        },
    }
    path = root / 'packet.json'
    path.write_text(json.dumps(packet), encoding='utf-8')
    return site, path, packet


class SourcePacketTests(unittest.TestCase):
    def test_all_six_case_sources_join(self):
        for case in trail.CASES:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as tmp:
                site, path, _ = fixture(Path(tmp), case)
                report = packet_module.verify_packet(site, path)
                self.assertEqual(set(report['source_sha256']), set(packet_module.RECORDS))
                trail.validate_source(site, case)

    def test_reject_record_tamper_and_unsigned_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, path, packet = fixture(root, trail.CASES[0])
            (root / 'official_plan_designation.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                packet_module.verify_packet(site, path)
            (root / 'official_plan_designation.txt').write_text('original-source-official_plan_designation-all_prerequisites')
            packet['assertions']['official_plan_designation'] = False
            path.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source assertion mismatch'):
                packet_module.verify_packet(site, path)

    def test_reject_source_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, path, packet = fixture(root, trail.CASES[0])
            packet['sources']['operator']['path'] = '../operator.txt'
            path.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'outside packet'):
                packet_module.verify_packet(site, path)
