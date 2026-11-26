"""Source-deferred bundles gate capture on original reviewed packet provenance."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from parking import CASES
from test_native_case_runner import CombinedAdapter
from test_reviewed_site import ReviewedSiteTests


class DeferredProductionTests(unittest.TestCase):
    def test_runner_rejects_diagnostic_packet_and_accepts_source_deferred_protocol(self):
        scratch = Path('.runtime-work/c150153-deferred-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, original = ReviewedSiteTests().make_packet(Path(temp))
            construction = json.loads((HERE / 'cases/west_inside/construction.deferred.primary.json').read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            self.assertEqual(construction['source_kind'], 'original_reviewed_site_deferred')
            self.assertNotIn(hashlib.sha256(packet.read_bytes()).hexdigest(), files['runner.py'])
            namespace = {'__name__': 'deferred_runner_test'}
            exec(compile(files['runner.py'], 'runner.py', 'exec'), namespace)
            case = next(item for item in CASES if item.id == 'west_inside')
            class ProtocolAdapter(CombinedAdapter):
                def provenance(self):
                    return 'original_native'
            site = dict(original['site'])
            site['site_sha256'] = hashlib.sha256(packet.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'external original reviewed site provenance required'):
                namespace['run'](ProtocolAdapter(site, case), packet, sources,
                                 Path(temp) / 'rejected-history.jsonl')
            self.assertFalse((Path(temp) / 'rejected-history.jsonl').exists())
            original['source_provenance'] = {'kind': 'original_reviewed_site',
                                             'diagnostic_fixture': False,
                                             'reviewer': 'synthetic protocol reviewer',
                                             'citation': 'synthetic protocol source'}
            packet.write_text(json.dumps(original) + '\n')
            site['site_sha256'] = hashlib.sha256(packet.read_bytes()).hexdigest()
            proof = namespace['run'](ProtocolAdapter(site, case), packet, sources,
                                     Path(temp) / 'history.jsonl')
            self.assertEqual(proof['frame_count'], 900)
            self.assertEqual(proof['case_id'], construction['case_id'])


if __name__ == '__main__':
    unittest.main()
