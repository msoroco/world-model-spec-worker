"""Synthetic reviewed-site packets test source-gated bundle generation only."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_source_bound_bundles import generate
from parking import CASES
from test_native_case_runner import CombinedAdapter
from test_reviewed_site import ReviewedSiteTests


class SourceBoundBundleTests(unittest.TestCase):
    def test_twelve_exact_draft_bundles_and_source_rejection(self):
        scratch = Path('.runtime-work/c150153-source-bound-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, _ = ReviewedSiteTests().make_packet(Path(temp))
            output = Path(temp) / 'bundles'
            index = generate(packet, sources, 4.0, output)
            self.assertEqual(index['status'], 'unselected_original_capture_pending')
            self.assertEqual(len(index['cases']), 12)
            self.assertEqual(len({entry['case_id'] for entry in index['cases']}), 12)
            staged = json.loads((output / 'manifest.draft.json').read_text())
            self.assertEqual(staged['status'], 'unselected_original_capture_pending')
            self.assertEqual(staged['cases'], index['cases'])
            for entry in index['cases']:
                raw = (output / entry['construction']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['construction_sha256'])
                files = {item['path']: item['content'] for item in json.loads(raw)['files']}
                self.assertIn('native_case_runner.py', files)
                self.assertIn('seal_original_capture.py', files)
                self.assertIn('physical_review.py', files)
                self.assertIn('measurement-contract.json', files)
                contract = json.loads(files['measurement-contract.json'])
                self.assertEqual(contract['case_id'], entry['case_id'])
                self.assertEqual(hashlib.sha256(files['measurement-contract.json'].encode()).hexdigest(),
                                 entry['measurement_contract_sha256'])
                self.assertEqual(contract['negative']['remove'], ['reviewed-site/packet.json'])
                self.assertEqual(hashlib.sha256((output / entry['measurement_contract']).read_bytes()).hexdigest(),
                                 entry['measurement_contract_sha256'])
                self.assertEqual(entry['measurement_procedure']['entrypoint'], 'analysis.py')
                description = json.loads(files['config.json'])['recording_description']
                expected = {item['name'] for item in description['channels'] + description['context_inputs']}
                self.assertEqual(set(entry['acquisition']), expected)
                self.assertIn('original_native', files['runner.py'])
                compile(files['runner.py'], 'runner.py', 'exec')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                generate(packet, sources, 4.0, output)
            source = next(Path(sources).iterdir())
            source.write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                generate(packet, sources, 4.0, Path(temp) / 'changed')

    def test_generated_runner_requires_original_provenance_and_pinned_site(self):
        scratch = Path('.runtime-work/c150153-source-bound-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, site_packet = ReviewedSiteTests().make_packet(Path(temp))
            output = Path(temp) / 'bundles'
            index = generate(packet, sources, 4.0, output)
            entry = next(item for item in index['cases'] if item['case_id'].endswith('__west_inside'))
            files = {item['path']: item['content'] for item in
                     json.loads((output / entry['construction']).read_text())['files']}
            namespace = {'__name__': 'source_bound_runner_test'}
            exec(compile(files['runner.py'], 'runner.py', 'exec'), namespace)
            case = next(item for item in CASES if item.id == 'west_inside')
            site = dict(site_packet['site'])
            site['site_sha256'] = hashlib.sha256(packet.read_bytes()).hexdigest()
            fake = CombinedAdapter(site, case)
            with self.assertRaisesRegex(ValueError, 'original Native adapter provenance required'):
                namespace['run'](fake, packet, sources, Path(temp) / 'bad-history.jsonl')
            class ProtocolAdapter(CombinedAdapter):
                def provenance(self):
                    return 'original_native'
            original_protocol = ProtocolAdapter(site, case)
            proof = namespace['run'](original_protocol, packet, sources,
                                     Path(temp) / 'history.jsonl')
            self.assertEqual(proof['frame_count'], 900)
            self.assertEqual(proof['case_id'], entry['case_id'])
            packet.write_text(packet.read_text().replace('fixture test', 'changed reviewer'))
            with self.assertRaisesRegex(ValueError, 'reviewed original site packet changed'):
                namespace['run'](original_protocol, packet, sources,
                                 Path(temp) / 'changed-history.jsonl')

    def test_pinned_offline_on_all_source_bound_drafts(self):
        scratch = Path('.runtime-work/c150153-source-bound-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, _ = ReviewedSiteTests().make_packet(Path(temp))
            output = Path(temp) / 'bundles'
            index = generate(packet, sources, 4.0, output)
            manifest = output / 'manifest.draft.json'
            for entry in index['cases']:
                with self.subTest(case=entry['case_id']):
                    command = [str(HERE.parents[1] / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                               '--manifest', str(manifest), '--case', entry['case_id'],
                               '--output', str(Path(temp) / ('offline-' + entry['case_id'].rsplit('__', 1)[-1]))]
                    result = subprocess.run(command, capture_output=True, text=True,
                                            cwd=HERE.parents[1], timeout=90)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('offline_passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
