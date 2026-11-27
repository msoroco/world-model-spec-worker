import json,unittest
from pathlib import Path
import runner

class TestSelected(unittest.TestCase):
    def test_static_route_and_capture(self):
        config=json.loads(Path('config.json').read_text())
        proof=runner.check(config['case_id'])
        self.assertEqual(len(runner.CAMERAS),4)
        self.assertEqual(config['duration_s'],30)
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['selected_case_id'],config['case_id'])
        self.assertEqual(config['controller']['candidate_id'],config['candidate_id'])
        self.assertTrue(proof)

if __name__=='__main__':unittest.main()
