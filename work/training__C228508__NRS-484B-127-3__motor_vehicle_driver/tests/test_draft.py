import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check
from engineering import commanded_centers, clear_spaces, FRAMES, GAP_TARGETS_M, CANDIDATES

class Construction(unittest.TestCase):
    def test_exact_case_and_candidate(self):
        config=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        result=check(config)
        self.assertEqual(result['engineering']['frames'],600)
        self.assertTrue(result['camera_capture_implemented'])
        suffix=config['case_suffix'];candidate=config['candidate_id']
        for frame in (0,299,599):
            gaps=clear_spaces(commanded_centers(suffix,candidate,frame))
            self.assertTrue(all(abs(v-GAP_TARGETS_M[suffix])<1e-8 for v in gaps.values()))
        self.assertEqual(len(CANDIDATES),2)
        self.assertEqual(FRAMES,600)

if __name__=='__main__': unittest.main()
