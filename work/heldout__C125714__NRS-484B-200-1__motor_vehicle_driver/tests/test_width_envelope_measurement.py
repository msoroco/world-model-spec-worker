import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from width_envelope_measurement import measure_width


class WidthEnvelopeTests(unittest.TestCase):
    def test_measures_narrower_half_without_legal_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'road.jsonl'
            source=json.loads((ROOT/'left-diagnostic.json').read_text())
            rows=[json.loads(line) for line in source['files']['directed_roadway_footprints.jsonl'].splitlines()]
            for row in rows:
                row['left_road_edge_xy']=[0,-2.2]
                row['right_road_edge_xy']=[0,2.2]
                row['subject_lane_width_m']=2.2
                row['opposite_lane_width_m']=2.2
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            measured=measure_width(path)
            self.assertAlmostEqual(measured['minimum_roadway_width_m'],4.4)
            self.assertFalse(measured['legal_sufficiency_decided'])
            rows[0]['subject_lane_width_m']=3.5
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'inconsistent'):
                measure_width(path)


if __name__=='__main__':
    unittest.main()
