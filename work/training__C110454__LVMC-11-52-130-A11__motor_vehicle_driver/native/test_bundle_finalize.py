import json
from pathlib import Path
import tempfile
import unittest

from finalize import measure_case_sources


class SavedParkingContract(unittest.TestCase):
    def test_positive_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source=root/'native_parking_history.json'
            rows=[]
            for i in range(480):
                x=25.0
                rows.append({'video_frame':i,'native_frame':100+i,'time_s':.05*(i+1),
                    'body_xy_m':[[x-2.6,-6.35],[x-2.6,-4.15],
                                 [x+2.6,-4.15],[x+2.6,-6.35]],
                    'speed_m_s':0.0 if i>=400 else 5.0})
            source.write_text(json.dumps({'source_kind':'native_frame_schema',
                'intersection_boundary_source':'native_map_readback',
                'intersection_entry_boundary_x_m':7.0,'frames':rows}))
            result=measure_case_sources(root)
            self.assertEqual(result['value']['sampled_relation'],'outside_15_ft')
            source.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure_case_sources(root)


if __name__=='__main__':
    unittest.main()
