import json
import unittest
from pathlib import Path
class BundleTest(unittest.TestCase):
 def test_exact_selected_config_and_site(self):
  root=Path(__file__).resolve().parents[1]
  entry=json.loads((root/'execution-manifest.json').read_text())['cases'][0]
  construction=json.loads((root/entry['construction']).read_text())
  files={item['path']:item['content'] for item in construction['files']}
  config=json.loads(files['config.json'])
  site=json.loads(files['site.json'])
  self.assertEqual(config['selected_case_id'],root.name+'__yield_ego_left_near_time')
  self.assertEqual(site['review_status'],'reviewed_candidate')
  self.assertEqual(len([name for name in files if name.startswith('review/')]),5)
