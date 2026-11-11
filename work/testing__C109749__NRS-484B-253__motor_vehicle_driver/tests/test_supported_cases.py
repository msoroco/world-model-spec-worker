import json
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]


class SupportedCasesTest(unittest.TestCase):
    def test_root_and_primary_candidates_cover_selected_cases(self):
        manifest = json.loads((FOLDER/'execution-manifest.json').read_text())
        expected = [entry['case_id'] for entry in manifest['cases']]
        root_config = json.loads((FOLDER/'config.json').read_text())
        self.assertEqual(root_config['supported_case_ids'], expected)
        primary = manifest['cases'][0]
        for candidate in [primary, *primary['candidates']]:
            bundle = json.loads((FOLDER/candidate['construction']).read_text())
            configs = [file for file in bundle['files'] if file['path']=='config.json']
            self.assertEqual(len(configs), 1)
            config = json.loads(configs[0]['content'])
            self.assertEqual(config['supported_case_ids'], expected)
            self.assertEqual(config['selected_case_id'], primary['case_id'])
        primary_bundle = json.loads((FOLDER/primary['construction']).read_text())
        primary_config = next(file['content'] for file in primary_bundle['files']
                              if file['path']=='config.json')
        self.assertEqual(json.loads(primary_config), root_config)
