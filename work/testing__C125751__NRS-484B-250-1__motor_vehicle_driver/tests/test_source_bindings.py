import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_protocol import load_case
from source_bindings import bind_sources, prepare_capture_spec, route_digest
from test_signal_crossing import MAP, REVIEW, packet


class SourceBindingTest(unittest.TestCase):
    def test_exact_source_bytes_and_tamper_rejection(self):
        scratch = ROOT.parents[1] / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            source = Path(temporary)
            p = packet()
            raw = json.dumps(p, sort_keys=True).encode()
            (source / 'map.xodr').write_bytes(MAP)
            (source / 'review.json').write_bytes(REVIEW)
            (source / 'source-packet.json').write_bytes(raw)
            spec = copy.deepcopy(load_case(ROOT, 'precedence'))
            spec.update(source_packet_sha256=hashlib.sha256(raw).hexdigest(),
                        map_sha256=hashlib.sha256(MAP).hexdigest(),
                        crossing_id=p['crossing_id'],
                        ego_route_sha256=route_digest(p['ego_route_xy_m']),
                        other_route_sha256=route_digest(p['other_route_xy_m']),
                        ego_blueprint='vehicle.cpu.fixture.ego',
                        other_blueprint='vehicle.cpu.fixture.other')
            self.assertEqual(bind_sources(spec, 'precedence', source,
                                          ROOT / 'camera-plan.json')['crossing_id'], 'median-1')
            planning = load_case(ROOT, 'precedence')
            resolved = prepare_capture_spec(
                planning, 'precedence', source, ROOT / 'camera-plan.json',
                {'ego': 'vehicle.cpu.fixture.ego',
                 'other': 'vehicle.cpu.fixture.other'})
            self.assertEqual(resolved['source_packet_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(resolved['crossing_id'], p['crossing_id'])
            with self.assertRaisesRegex(ValueError, 'blueprint missing'):
                prepare_capture_spec(planning, 'precedence', source,
                                     ROOT / 'camera-plan.json', {'ego': None, 'other': None})
            spec_path = source / 'case-spec.json'
            spec_path.write_text(json.dumps(spec))
            checked = subprocess.run([sys.executable, str(ROOT / 'runner.py'),
                '--check', '--case-spec', str(spec_path), '--sources', str(source),
                '--camera-plan', str(ROOT / 'camera-plan.json')],
                capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertFalse(json.loads(checked.stdout)['native_started'])
            (source / 'map.xodr').write_bytes(MAP + b' ')
            rejected = subprocess.run([sys.executable, str(ROOT / 'runner.py'),
                '--check', '--case-spec', str(spec_path), '--sources', str(source),
                '--camera-plan', str(ROOT / 'camera-plan.json')],
                capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                bind_sources(spec, 'precedence', source, ROOT / 'camera-plan.json')
            (source / 'map.xodr').write_bytes(MAP)
            (source / 'review.json').write_bytes(REVIEW + b' ')
            with self.assertRaisesRegex(ValueError, 'review hash mismatch'):
                bind_sources(spec, 'precedence', source, ROOT / 'camera-plan.json')
            (source / 'review.json').write_bytes(REVIEW)
            spec['crossing_id'] = 'another-crossing'
            with self.assertRaisesRegex(ValueError, 'source binding differs'):
                bind_sources(spec, 'precedence', source, ROOT / 'camera-plan.json')


if __name__ == '__main__':
    unittest.main()
