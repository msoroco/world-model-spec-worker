import json
import tempfile
import unittest
from pathlib import Path

from measure_native import analyze


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value)+'\n')


def put_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(value)+'\n' for value in values))


def box(x,y):
    return [[x-1,y-1,0],[x+1,y-1,0],[x+1,y+1,0],[x-1,y+1,0]]


def create(root):
    config={'case_id':'training__C104538__NRS-484B-407__motor_vehicle_driver__below_500_ft',
            'candidate_id':'primary','duration_s':3,'rate_hz':1}
    put(root/'config.json',config)
    native_road=root/'native_road_readback.xodr';native_road.write_text('native road')
    import hashlib
    road_sha=hashlib.sha256(native_road.read_bytes()).hexdigest()
    barrier=lambda x:{'requested':{'native_xyz_m':[x,0,0]},
                      'world_vertices_m':box(x,0)}
    put(root/'native-construction-context.json',{'case_id':config['case_id'],
        'candidate_id':'primary','native_road_sha256':road_sha,
        'barrier_inventory':[barrier(0),barrier(2)],
        'waypoint_elevation_samples':[{'native_waypoint_z_m':0,
            'authored_road_height_m':0},{'native_waypoint_z_m':3.25,
            'authored_road_height_m':3.2}]})
    trace=[];evidence=[];history=[];viewpoints=[];mapping=[]
    for i,(x,heading) in enumerate(((0,0),(3,90),(6,180))):
        frame=101+i;time=float(i+1);body=box(x,0)
        views={role:{'driver_viewpoint_xyz_m':[x+100,10,4]}
               for role in ('reference_left','reference_right')}
        motion={'ego_body_vertices_m':body}
        trace.append({'frame':frame,'time_s':time,'position_m':[x,0,0],
            'velocity_mps':[1,0,0],'c104538_native':motion,
            'approaching_driver_views':views})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body}})
        history.append({'native_frame':frame,'time_s':time,
            'ego_body_vertices_m':body,'ego_heading_deg':heading,
            'ego_center_xyz_m':[x,0,0]})
        viewpoints.append({'native_frame':frame,'time_s':time,'views':views})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,
                        'time_s':time})
    for name,values in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                        ('native_body_history.jsonl',history),('driver_eye_rays.jsonl',viewpoints),
                        ('video_frames.jsonl',mapping)]:put_rows(root/name,values)


class SavedMeasurementTest(unittest.TestCase):
    def test_source_bound_turn_and_distinct_physical_triggers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);create(root);value=analyze(root)
            self.assertTrue(value['engineering_reversal_observed'])
            self.assertTrue(value['reverse_motion_observed'])
            self.assertFalse(value['fallback1_trigger_measured'])
            self.assertFalse(value['fallback2_trigger_measured'])
            self.assertFalse(value['fallback3_original_pixel_trigger_measured'])
            self.assertFalse(value['actual_body_visibility_proven'])
            context=json.loads((root/'native-construction-context.json').read_text())
            context['waypoint_elevation_samples'][1]['native_waypoint_z_m']=3.5
            put(root/'native-construction-context.json',context)
            self.assertTrue(analyze(root)['fallback1_trigger_measured'])
            context['barrier_inventory'][1]['requested']['native_xyz_m'][0]=2.2
            context['barrier_inventory'][1]['world_vertices_m']=box(2.2,0)
            put(root/'native-construction-context.json',context)
            self.assertTrue(analyze(root)['fallback2_trigger_measured'])

    def test_changed_body_and_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);create(root)
            evidence=[json.loads(s) for s in (root/'capture/evidence.jsonl').read_text().splitlines()]
            evidence[1]['ego']['body_vertices_m'][0][0]+=1
            put_rows(root/'capture/evidence.jsonl',evidence)
            with self.assertRaisesRegex(ValueError,'ego body differs'):analyze(root)
            (root/'capture/evidence.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):analyze(root)


if __name__=='__main__':unittest.main()
