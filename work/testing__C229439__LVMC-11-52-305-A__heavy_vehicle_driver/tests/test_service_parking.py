"""Focused construction and numeric-source checks for commercial service parking."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from service_parking import CASES, SOURCE_FIELDS, construct, measure_original, validate_scene


class FakeAdapter:
    def __init__(self):self.calls=[];self.next_id=0
    def _new(self,name,*args):
        self.calls.append((name,args));self.next_id+=1;return self.next_id
    def spawn_device(self,*args):return self._new('device',*args)
    def spawn_vehicle(self,*args):return self._new('heavy_vehicle',*args)
    def spawn_worksite(self,*args):return self._new('worksite',*args)
    def spawn_worker(self,*args):return self._new('worker',*args)
    def set_parking_route(self,*args):self.calls.append(('parking_route',args))
    def set_work_activity(self,*args):self.calls.append(('work_activity',args))
    def destroy(self,actor):self.calls.append(('destroy',(actor,)))


def fixture(case):
    import hashlib
    scene={'cell_id':'C229439','actor':'heavy_vehicle_driver',
           'vehicle_id':'synthetic-heavy-v1','driver_id':'synthetic-driver',
           'worker_id':'synthetic-worker','heavy_vehicle_blueprint':'vehicle.carlamotors.carlacola',
           'work_order_id':'synthetic-order','work_activity_description':'synthetic task',
           'parking_device_text':'No heavy parking except posted permission',
           'commercial_vehicle':True,'street_public':True,'city_jurisdiction':True,
           'school_public':True,'business_district':False,'mainly_residential':True,
           'governed_curb_rect_m':[0.,0.,3.,6.],
           'vehicle_footprint_rect_m':[.2,.2,2.,4.],
           'vehicle_center_xy':[1.,1.],
           'worksite_xy':[4.,1.] if case.work_near else [200.,1.],
           'parking_route_xy':[[-2.,-2.],[1.,1.]],'park_start_frame':2}
    for name in ('work_kind','work_near','length_ft','unladen_lb','adjacent_kind',
                 'frontage_ft','posted_permission','loading'):
        scene[name]=getattr(case,name)
    for field in SOURCE_FIELDS:
        scene[field+'_source_sha256']=hashlib.sha256((case.name+field).encode()).hexdigest()
    rows=[]
    for index in range(9):
        row={'original_frame':100+index,'time_s':index/20,
             'speed_mps':1. if index<2 else 0.,
             'work_active':case.work_kind!='none',
             'vehicle_center_xy':scene['vehicle_center_xy'],
             'worksite_xy':scene['worksite_xy'],
             'vehicle_footprint_rect_m':scene['vehicle_footprint_rect_m']}
        for key in ('vehicle_id','driver_id','worker_id','work_kind','length_ft',
                    'unladen_lb','adjacent_kind','frontage_ft','posted_permission','loading'):
            row[key]=scene[key]
        for field in SOURCE_FIELDS:
            row[field+'_source_sha256']=scene[field+'_source_sha256']
        rows.append(row)
    return scene,rows


class ServiceParkingTest(unittest.TestCase):
    def test_all_selected_cases_construct_actual_worksite(self):
        self.assertEqual(len(CASES),18)
        for case in CASES:
            with self.subTest(case=case.name):
                scene,rows=fixture(case);validate_scene(scene,case)
                adapter=FakeAdapter();built=construct(adapter,scene,case)
                self.assertEqual(len(built['owned']),4)
                self.assertEqual([x[0] for x in adapter.calls[:4]],['device','heavy_vehicle','worksite','worker'])
                self.assertIn('work_activity',[x[0] for x in adapter.calls])
                measured=measure_original(rows,scene,case,diagnostic_frames=9)
                self.assertEqual(measured['length_ft'],case.length_ft)
                self.assertEqual(measured['unladen_lb'],case.unladen_lb)
                self.assertEqual(measured['residential_frontage_ft'],case.frontage_ft)
                self.assertIsNone(measured['immediate_neighborhood_judgment'])

    def test_source_and_work_readback_rejections(self):
        case=CASES[0];scene,rows=fixture(case)
        del scene[SOURCE_FIELDS[0]+'_source_sha256']
        with self.assertRaisesRegex(ValueError,'reviewed source missing'):
            validate_scene(scene,case)
        scene,rows=fixture(case);rows[3]['work_active']=False
        with self.assertRaisesRegex(ValueError,'actual work activity differs'):
            measure_original(rows,scene,case,diagnostic_frames=9)

    def test_numerical_boundary_is_measured_not_judged(self):
        by_name={c.name:c for c in CASES}
        self.assertEqual([by_name[n].length_ft for n in ('length_23_9ft','length_24_0ft','length_24_1ft')],[23.9,24.,24.1])
        self.assertEqual([by_name[n].unladen_lb for n in ('weight_7999lb','weight_8000lb','weight_8001lb')],[7999.,8000.,8001.])
        self.assertEqual([by_name[n].frontage_ft for n in ('residence_299ft','residence_300ft','residence_301ft')],[299.,300.,301.])


if __name__=='__main__':unittest.main()
