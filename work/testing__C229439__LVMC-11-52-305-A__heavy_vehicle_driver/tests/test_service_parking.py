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
    spec=ROOT/'diagnostics'/case.name/'diagnostic.json'
    data=json.loads(spec.read_text())['files']
    scene=json.loads(data['service-parking-context.json'])['scene']
    rows=[json.loads(s) for s in data['original-service-parking.jsonl'].splitlines()]
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
