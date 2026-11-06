import json
from pathlib import Path
import tempfile
import unittest

from finalize import measure_approach


class SavedMeasurement(unittest.TestCase):
    def test_positive_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'native_samples.jsonl'
            rows = []
            for index in range(4):
                x = -25 + index
                rows.append({'video_frame':index, 'native_frame':100+index,
                             'time_s':index*.05, 'speed_m_s':5,
                             'two_way_native_survey':True,
                             'body_xy_m':[[x-2.6,.65],[x-2.6,2.85],
                                          [x+2.6,2.85],[x+2.6,.65]]})
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            (root / 'road_geometry.json').write_text(json.dumps({
                'intersection_entry_point_native_m':[-7,0],
                'road_directions_native':{k:[1,0] for k in
                    ('approach_forward','approach_opposing',
                     'destination_forward','destination_opposing')}}))
            result = measure_approach(root)
            self.assertEqual(result['value']['sampled_relation'],'within_100_ft')
            source.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure_approach(root)


if __name__ == '__main__':
    unittest.main()
