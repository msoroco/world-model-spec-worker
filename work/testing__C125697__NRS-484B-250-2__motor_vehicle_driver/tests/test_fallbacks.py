import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO/'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def configuration(construction):
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


class Fallbacks(unittest.TestCase):
    def test_exact_case_risk_and_isolated_changes(self):
        entry = json.loads((HERE/'execution-manifest.json').read_text())['cases'][0]
        self.assertEqual(validate(HERE, entry, 'NRS-484B-250-2', 'C125697',
                                  required=True, require_alternate=True,
                                  candidate_count=4)['fallbacks'],
                         ['fallback1', 'fallback2', 'fallback3'])
        original = configuration(json.loads((HERE/'construction.json').read_text()))
        for candidate in entry['candidates']:
            changed = configuration(json.loads((HERE/candidate['construction']).read_text()))
            ident = candidate['id']
            if ident == 'fallback1':
                self.assertEqual(changed['site']['other_approach'][1], -14)
                self.assertEqual(changed['site']['routes']['other'][0][1], -14)
                changed['site']['other_approach'] = original['site']['other_approach']
                changed['site']['routes']['other'][0] = original['site']['routes']['other'][0]
            elif ident == 'fallback2':
                self.assertNotEqual(changed['site']['cameras']['approach'],
                                    original['site']['cameras']['approach'])
                changed['site']['cameras']['approach'] = original['site']['cameras']['approach']
            else:
                self.assertEqual(changed['ego_release_frame'], 24)
                changed['ego_release_frame'] = original['ego_release_frame']
            # Source packet hashes change when the site changes; all behavioral
            # and capture fields outside the declared engineering knob stay fixed.
            changed.pop('site_review')
            original_copy = dict(original)
            original_copy.pop('site_review')
            for key in ('crossing_polygon_source', 'approach_geometry_source',
                        'median_spacing_source', 'all_entrances_source',
                        'signal_governance_source', 'signal_head_video_source'):
                self.assertEqual(changed['site'][key], original['site'][key])
            self.assertEqual(changed, original_copy)
