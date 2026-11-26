import importlib.util
from pathlib import Path
import sys
import unittest


path=Path(__file__).resolve().parents[1]/'curb_entry.py'
spec=importlib.util.spec_from_file_location('curb_entry',path)
probe=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=probe
spec.loader.exec_module(probe)


def scene(case):
    s=dict(cell_id='C228096',actor='pedestrian',pedestrian_person=True,
           vehicle_qualifies=True,driver_in_control=True,
           action=case.action,vehicle_gap=case.vehicle_gap,
           route_kind=case.route_kind,road_rect_m=[-10,-2,10,2],
           vehicle_path_rect_m=[-10,-.5,10,.5],
           curb_start_xy=[0,-3],departure_frame=round(case.departure_hold_s*20)
           if case.departure_hold_s is not None else 100,
           pedestrian_route_xy=[[0,-3],[1,-3] if case.route_kind=='curb' else
                                [0,-1] if case.route_kind=='road_only' else [0,0]],
           vehicle_route_xy=[[-case.vehicle_start_gap_m,0],[10,0]]
           if case.vehicle_start_gap_m is not None else [[-10,0],[10,0]],
           vehicle_id='car',driver_id='driver')
    for field in ('pedestrian_identity','curb_safety','road_boundary',
                  'vehicle_path','vehicle_motion','driver_control',
                  'pedestrian_route','departure_timing','introductory_exceptions'):
        s[field+'_source_sha256']='a'*64
    return s


def rows(case,s):
    out=[]
    depart=s['departure_frame']
    for i in range(900):
        y=-3 if i<depart else (-1 if case.route_kind=='road_only' else
                             -3 if case.route_kind=='curb' else
                             -1 if i<depart+100 else 0)
        row=dict(original_frame=1000+i,time_s=i/20,
                 pedestrian_id='ped',vehicle_id='car',action=case.action,
                 pedestrian_xy=[0,y],
                 vehicle_xy=[case.vehicle_start_gap_m if case.vehicle_start_gap_m is not None
                             else 1 if case.vehicle_gap=='close' else 20,0],
                 pedestrian_speed_mps=2 if case.action=='run' else 1,
                 vehicle_speed_mps=5,
                 vehicle_path_source_sha256=s['vehicle_path_source_sha256'])
        for field in ('frame','pedestrian_motion','vehicle_motion',
                      'road_boundary','curb_safety','vehicle_path',
                      'driver_control','introductory_exceptions'):
            row[field+'_source_sha256']='a'*64
        out.append(row)
    return out


class Adapter:
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def __getattr__(self,name):
        def invoke(*args):
            self.calls.append((name,args))
            if name=='spawn_vehicle' and self.fail:return None
            if name.startswith('spawn_'):return name
        return invoke


class EntryTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s=scene(case);a=Adapter()
                probe.construct(a,s,case)
                self.assertIn('set_pedestrian_route',[x[0] for x in a.calls])
                result=probe.measure_original(rows(case,s),s,case)
                self.assertEqual(result['vehicle_path_entry_frame'] is not None,
                                 case.route_kind=='path')
                self.assertIsNone(result['impossible_to_yield_judgment'])

    def test_missing_source_and_path_rejected(self):
        case=probe.CASES[0];s=scene(case);data=rows(case,s)
        del data[4]['vehicle_motion_source_sha256']
        with self.assertRaisesRegex(ValueError,'source missing'):
            probe.measure_original(data,s,case)
        data=rows(case,s)
        for row in data:
            if row['pedestrian_xy'][1]==0:row['pedestrian_xy']=[0,-1]
        with self.assertRaisesRegex(ValueError,'path entry missing'):
            probe.measure_original(data,s,case)

    def test_driver_and_cleanup(self):
        case=probe.CASES[0];s=scene(case);s['driver_in_control']=False
        with self.assertRaisesRegex(ValueError,'driver/vehicle'):
            probe.validate_scene(s,case)
        a=Adapter(fail=True)
        with self.assertRaisesRegex(ValueError,'vehicle spawn failed'):
            probe.construct(a,scene(case),case)
        self.assertEqual(a.calls[-1][0],'destroy')

    def test_case_routes_are_physically_distinct(self):
        for case in probe.CASES:
            s=scene(case)
            self.assertEqual(probe.validate_scene(s,case)['case_id'],case.name)
        wrong=scene(probe.CASES[3])
        wrong['pedestrian_route_xy']=[[0,-3],[0,0]]
        with self.assertRaisesRegex(ValueError,'road-only route enters vehicle path'):
            probe.validate_scene(wrong,probe.CASES[3])
        wrong=scene(probe.CASES[4])
        wrong['pedestrian_route_xy']=[[0,-3],[0,-1]]
        with self.assertRaisesRegex(ValueError,'curb-stay route leaves'):
            probe.validate_scene(wrong,probe.CASES[4])


if __name__=='__main__':unittest.main()
