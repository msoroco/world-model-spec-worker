import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runner import check_config, resolve_survey
from fire_station_finalizer import analyze


def ref(road,lane,s): return {'road_id':road,'lane_id':lane,'s':s}
SOURCE={'kind':'operator_survey','asset_id':'test-station','source_sha256':'1'*64}
SURVEY={'map_name':'test-map','station_source':SOURCE,
        'public_before':ref(7,1,0),'public_at':ref(7,1,8),
        'public_after':ref(7,1,16),'driveway_at':ref(8,2,6),
        'routes':{'through_driveway':[ref(7,1,0),ref(8,2,6),ref(7,-1,0)]}}


class RunnerAndFinalizerTest(unittest.TestCase):
    def config(self):
        return {'case_branch':'through_driveway',
          'selected_case_id':'heldout__C104538__LVMC-11-12-060__motor_vehicle_driver__through_driveway',
          'law_id':'LVMC-11-12-060','cell_id':'C104538','actor':'motor_vehicle_driver',
          'rate_hz':20,'frames':240,'duration_s':12,
          'cameras':[{'name':n} for n in ('overview','approach','reference_corner','driver_reference')],
          'station_survey':SURVEY,'target_speed_mps':3.0}

    def test_route_requires_mapped_driveway_and_station_source(self):
        self.assertTrue(check_config(self.config()))
        bad=self.config();bad['station_survey']=dict(SURVEY,station_source={})
        def waypoint(road,lane,s):
            return SimpleNamespace(road_id=road,lane_id=lane,s=s,lane_width=3.0,
                transform=SimpleNamespace(location=SimpleNamespace(
                    x=s if road==7 else 8,y=0 if road==7 else s)))
        world_map=SimpleNamespace(name='test-map',get_waypoint_xodr=waypoint)
        with self.assertRaisesRegex(ValueError,'source-bound'):
            resolve_survey(world_map,bad['station_survey'],'through_driveway')
        bad=self.config();survey=dict(SURVEY,routes={'through_driveway':[ref(7,1,0),ref(7,1,8),ref(7,-1,0)]});bad['station_survey']=survey
        with self.assertRaisesRegex(ValueError,'never enters'):
            check_config(bad)
        for key,value,error in (('spawn_height_m',.7,'spawn height'),
                                ('waypoint_arrival_m',.5,'arrival radius'),
                                ('speed_gain',0,'speed gain')):
            invalid=self.config();invalid[key]=value
            with self.assertRaisesRegex(ValueError,error):check_config(invalid)

    def test_survey_resolves_both_public_approach_directions(self):
        def waypoint(road,lane,s):
            x = s if lane > 0 else 16-s
            return SimpleNamespace(road_id=road,lane_id=lane,s=s,lane_width=3.0,
                transform=SimpleNamespace(location=SimpleNamespace(
                    x=x if road==7 else 8,y=0 if road==7 else s)))
        world_map=SimpleNamespace(name='test-map',get_waypoint_xodr=waypoint)
        east=resolve_survey(world_map,SURVEY,'through_driveway')
        self.assertEqual(east[0]['public_lane'],(7,1))
        west=dict(SURVEY,public_before=ref(7,-1,0),public_at=ref(7,-1,8),
                  public_after=ref(7,-1,16),
                  routes={'through_driveway':[ref(7,-1,0),ref(8,2,6),ref(7,1,0)]})
        opposite=resolve_survey(world_map,west,'through_driveway')
        self.assertEqual(opposite[0]['public_lane'],(7,-1))
        self.assertNotEqual(east[0]['public_lane'],opposite[0]['public_lane'])

    def test_saved_finalizer_rejects_missing_source_and_measures_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            config=self.config();config['case']={'recording_description':{'channels':[]}}
            (root/'config.json').write_text(json.dumps(config))
            context={'source':SOURCE,'entrance_xy_m':[0,0],
              'public_lane':[7,1],'driveway_lane':[8,2],
              'entrance_polygon_xy':[[-2,-2],[2,-2],[2,2],[-2,2]],
              'approach_polygon_xy':[[-8,-2],[0,-2],[0,2],[-8,2]]}
            (root/'station_context.json').write_text(json.dumps(context))
            def rows(items):return ''.join(json.dumps(item)+'\n' for item in items)
            fm=[];ps=[];trace=[]
            for i in range(4):
                t=i*.05;frame=100+i
                fm.append({'video_frame':i,'carla_frame':frame,'time_s':t})
                ps.append({'frame':frame,'time_s':t,'ego':{'actor_id':5,
                  'center_xy':[-3+i,0],'heading_rad':i*1.0,'speed_mps':3,
                  'lane_id':[8,2] if i==2 else [7,1],
                  'body_vertices_xy':[[-1,-1],[1,-1],[1,1],[-1,1]]}})
                trace.append({'frame':frame,'time_s':t})
            (root/'video_frames.jsonl').write_text(rows(fm))
            (root/'participant_state.jsonl').write_text(rows(ps))
            (root/'trace.jsonl').write_text(rows(trace))
            report=analyze(root)
            measurement=report['measurements']['station_reversal']['value']
            self.assertTrue(measurement['reversal_observed'])
            self.assertTrue(measurement['entered_driveway'])
            self.assertTrue(measurement['body_entrance_overlap_frames'])
            self.assertEqual(measurement['purpose_of_turning'],'unresolved_contextual_judgment')
            (root/'participant_state.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                analyze(root,write_channels=False)


if __name__=='__main__':unittest.main()
