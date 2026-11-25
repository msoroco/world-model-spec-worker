"""The bounded motion fallback keeps each response comparison controlled."""
import json
from pathlib import Path
import unittest


FOLDER = Path(__file__).resolve().parents[1]


def config(construction):
    return json.loads(next(row['content'] for row in construction['files']
                           if row['path'] == 'config.json'))


class CandidatePairTests(unittest.TestCase):
    def test_throttle_fallback_preserves_modality_pair_contracts(self):
        manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
        by_suffix = {entry['case_id'].removeprefix(FOLDER.name + '__'): entry
                     for entry in manifest['cases']}
        for prefix in ('', 'electric_bicycle__', 'electric_scooter__'):
            configs = []
            for mode in ('maintain_clearance', 'cross_rider_path'):
                entry = by_suffix[prefix + mode]
                self.assertEqual(entry['candidate_risk']['status'], 'physical')
                self.assertEqual(len(entry['candidates']), 1)
                primary = config(json.loads((FOLDER / entry['construction']).read_text()))
                fallback = config(json.loads((FOLDER / entry['candidates'][0]['construction']).read_text()))
                for key in ('cell_id', 'law_id', 'actor', 'selected_case_id',
                            'required_atoms', 'source_packets', 'rate_hz',
                            'duration_s', 'cameras', 'case', 'physical_completion'):
                    self.assertEqual(primary[key], fallback[key], key)
                self.assertEqual(primary['rider_throttle_scale'], 1.0)
                self.assertEqual(fallback['rider_throttle_scale'], 1.15)
                configs.append((primary, fallback))
            for key in ('cell_id', 'law_id', 'actor', 'required_atoms',
                        'source_packets', 'rate_hz', 'duration_s', 'cameras'):
                self.assertEqual(configs[0][0][key], configs[1][0][key], key)
                self.assertEqual(configs[0][1][key], configs[1][1][key], key)
            self.assertEqual(configs[0][0]['case']['rider_kind'],
                             configs[1][0]['case']['rider_kind'])
            self.assertEqual(configs[0][1]['rider_throttle_scale'],
                             configs[1][1]['rider_throttle_scale'])


if __name__ == '__main__':
    unittest.main()
