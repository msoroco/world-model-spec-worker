import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('device_lane_candidates',ROOT/'cases/core_device_lane/device_lane_candidates.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def body(x,speed):
    return {'position_m':[x,0,0],'yaw_deg':0,'speed_mps':speed,
            'body_corners_m':[[x+dx,dy,dz] for dx in (-2,2) for dy in (-1,1) for dz in (0,1)]}

class DeviceLaneCandidateTests(unittest.TestCase):
    def test_source_cited_control_and_marked_lane_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);following=root/'following_sources.jsonl';site=root/'device_lane_sources.jsonl'
            rows=[];signal=[]
            for i in range(4):
                rows.append({'frame':100+i,'time_s':i*.05,'ego':body(i*2,15),
                             'lead':body(i*2+10,5),'requested_phase':'first_closing_request',
                             'map_speed_limit_kmh':40})
                signal.append({'frame':100+i,'time_s':i*.05,'ego_station_m':5+i*5,
                               'stop_station_m':10,'native_light_state':'TrafficLightState.Red',
                               'lateral_center_shift_m':2 if i==3 else 0,
                               'marked_lane_width_m':3.5})
            signal[3]['ego_station_m']=750
            following.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            site.write_text(''.join(json.dumps(x)+'\n' for x in signal))
            events=module.derive(following,site)
            self.assertEqual([x['category'] for x in events if x['category'] in ('device','marked_lane')],['device','marked_lane'])
            self.assertTrue(all(x['source_sha256'] for x in events))
            signal[2]['frame']=105
            site.write_text(''.join(json.dumps(x)+'\n' for x in signal))
            with self.assertRaisesRegex(ValueError,'discontinuous'):
                module.derive(following,site)

if __name__=='__main__':unittest.main()
