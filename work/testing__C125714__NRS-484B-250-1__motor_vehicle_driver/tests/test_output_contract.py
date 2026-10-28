"""Synthetic contract fixtures exercise validation; they are not physics evidence."""
import copy,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import validate_output,measured_target,summarize
from recording import Resources
import execution

def jsonl(path,rows):path.write_text(''.join(json.dumps(r)+'\n' for r in rows))

class CompleteOutput(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='offline-contract-',dir=str(ROOT));cls.directory=Path(cls.temp.name);cls.video=cls.directory/'source.webm'
  command=['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=16x16:r=20','-frames:v','4','-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-y',str(cls.video)]
  subprocess.run(command,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def setUp(self):
  self.root=self.directory/'fixture';self.root.mkdir(exist_ok=True)
  cfg=json.loads((ROOT/'config.json').read_text());self.description=cfg['cases'][0]['recording_description'];self.times=[i*.05 for i in range(4)]
  trace=[{'frame':100+i,'time_s':t,'position':{'x':i,'y':0,'z':0},'heading_deg':0,'speed_mps':2.} for i,t in enumerate(self.times)]
  jsonl(self.root/'trace.jsonl',trace);jsonl(self.root/'map.jsonl',[{'video_frame':i,'carla_frame':100+i,'time_s':t} for i,t in enumerate(self.times)])
  channels=self.root/'channels';channels.mkdir(exist_ok=True);evidence=[]
  actor={'actor_id':1,'position_m':[0.,0.,0.],'heading_deg':0.,'velocity_mps':[2.,0.,0.],'speed_mps':2.,'vertices':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]}
  sample={'time_s':0.,'ego':actor,'participants':[actor,dict(actor,actor_id=2)],'road':{'road_id':1,'lane_id':-1,'lane_width_m':3.5,'station_m':300.,'forward':[1.,0.]},'weather':{'wetness':0.,'fog_density':0.},'devices':[],'lamps':0,'inside':[False,True],'distance_m':2.,'physical_dividers':[]}
  geometry={'intersection':[[0,0],[5,0],[5,5],[0,5]],'intersection_road_ids':[1,2],'participant_routes':[[1],[2]],'authored_context':{'synthetic_fixture':True},'surface_reference':'road.xodr','surface_provenance':{'synthetic_fixture':True}}
  for channel in self.description['channels']:
   name=channel['name'];jsonl(channels/(name+'.jsonl'),[{'time_s':t,'value':execution.project(channel['name'],sample,[],geometry)} for t in self.times]);evidence.append({'name':name,'unit':channel['unit'],'reference':'channels/'+name+'.jsonl'})
  context={c['name']:{'synthetic_fixture':True} for c in self.description['context_inputs']};(self.root/'context.json').write_text(json.dumps(context))
  evidence += [{'name':c['name'],'unit':c['unit'],'reference':'context.json'} for c in self.description['context_inputs']]
  for i in range(4):(self.root/('camera-'+str(i)+'.webm')).write_bytes(self.video.read_bytes())
  jsonl(self.root/'participants.jsonl',[{'time_s':t,'participants':[{'actor_id':1},{'actor_id':2}]} for t in self.times])
  jsonl(self.root/'footprint.jsonl',[{'time_s':t,'vertices':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]} for t in self.times])
  jsonl(self.root/'speed.jsonl',[{'time_s':t,'value':2.} for t in self.times]);(self.root/'cause.json').write_text('{"synthetic_fixture":true}')
  self.result={'setup_confirmed':True,'behavior_attempted':True,'maneuver_completed':True,'physical_failure_flags':[],'trace_reference':'trace.jsonl','video_frame_map_reference':'map.jsonl','video_references':['camera-'+str(i)+'.webm' for i in range(4)],'recording_evidence':evidence,'target_checks':[measured_target('speed',2.,2.,.1,'synthetic schema test',['cause.json'])],'required_participant_ids':[1,2],'participant_history_reference':'participants.jsonl','footprint_reference':'footprint.jsonl','driving_polygons':[[[-1,-1],[5,-1],[5,5],[-1,5]]],'realized_observables':{'speed':{'value':2.,'reference':'speed.jsonl','sample_window_s':[0.,.15],'statistic':'mean'}}}
 def test_complete_encoded_fixture_passes(self):self.assertTrue(validate_output(self.root,self.result,self.description))
 def test_null_channel_rejected(self):
  channel=self.description['channels'][0]['name'];jsonl(self.root/'channels'/(channel+'.jsonl'),[{'time_s':t,'value':None} for t in self.times])
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_requested_value_not_measured(self):
  self.result['target_checks'][0]['measured']=None
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_failed_target_rejected(self):
  self.result['target_checks'][0]['matched']=False
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_nonoriginal_timestamp_rejected(self):
  jsonl(self.root/'map.jsonl',[{'video_frame':i,'carla_frame':100+i,'time_s':t+.01} for i,t in enumerate(self.times)])
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_missing_participant_history_rejected(self):
  jsonl(self.root/'participants.jsonl',[{'time_s':t,'participants':[{'actor_id':1}]} for t in self.times])
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_footprint_departure_rejected(self):
  jsonl(self.root/'footprint.jsonl',[{'time_s':t,'vertices':[[1000,1000,0]]} for t in self.times])
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_png_directory_is_not_video(self):
  self.result['video_references']=['channels']
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_wrong_video_count_rejected(self):
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=16x16:r=20','-frames:v','2','-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-y',str(self.root/'camera-0.webm')],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_summary_not_substituted(self):
  self.result['realized_observables']['speed']['value']=8.
  with self.assertRaises(ValueError):validate_output(self.root,self.result,self.description)
 def test_cleanup_continues_after_exception(self):
  resources=Resources();called=[];resources.own(lambda:called.append('world_restored'));resources.own(lambda:(_ for _ in ()).throw(RuntimeError('sensor_error')));resources.own(lambda:called.append('capture_closed'))
  errors=resources.close();self.assertEqual(called,['capture_closed','world_restored']);self.assertEqual(len(errors),1);self.assertEqual(resources.close(),[])
 def test_convex_footprints_do_not_use_bounding_boxes(self):
  diamond=[[0,1],[1,0],[0,-1],[-1,0]];corner=[[.8,.8],[1,.8],[1,1],[.8,1]]
  self.assertFalse(execution.intersects(diamond,corner))
 def test_measured_summary_window(self):
  self.assertEqual(summarize([{'time_s':0.,'value':2.},{'time_s':.05,'value':4.}],0.,.05),(3.,[0.,.05]))
 def test_no_unknown_projection_can_become_null(self):
  with self.assertRaises(execution.CapabilityError):execution.project('unknown.atom',{},[],{})
