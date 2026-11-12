import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_sight_comparison import audit,read


class SightComparisonTests(unittest.TestCase):
    def test_below_at_above_and_tampered_body_ray(self):
        self.assertEqual(audit()['boundary_probe_m'],[152.0,152.4,152.8])
        diagnostic=copy.deepcopy(read('diagnostic-prohibition_407.json'))
        rows=[json.loads(line) for line in
              diagnostic['files']['capture/evidence.jsonl'].splitlines()]
        rows[0]['visibility']['approaches'][0]['body_rays_at_probe'].pop()
        diagnostic['files']['capture/evidence.jsonl']='\n'.join(map(json.dumps,rows))+'\n'
        with self.assertRaisesRegex(ValueError,'nine-body-ray'):
            audit(candidate_diagnostic=diagnostic)

    def test_changed_motion_rejected(self):
        diagnostic=copy.deepcopy(read('diagnostic-prohibition_407.json'))
        diagnostic['files']['u_turn_motion.jsonl']+='\n'
        with self.assertRaisesRegex(ValueError,'motion, cameras or map'):
            audit(candidate_diagnostic=diagnostic)


if __name__=='__main__':unittest.main()
