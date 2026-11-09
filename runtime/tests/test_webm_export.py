"""Exercise the installed encoder and confirm playback preserves source frames."""
import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from convert_demo_videos import convert
from review_recordings import render

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class WebmExportTest(unittest.TestCase):
 def test_preview_is_separate_and_primary_cannot_hide_trace_frames(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'raw.mkv'
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=green:s=320x180:r=20','-frames:v','4','-c:v','ffv1',str(source)],check=True)
   trace=[{'frame':i+10,'time_s':(i+1)*.05,'speed_mps':2} for i in range(4)]
   mapping=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(trace)]
   for name,values in [('trace.jsonl',trace),('video_frames.jsonl',mapping)]:
    (root/name).write_text('\n'.join(json.dumps(r) for r in values)+'\n')
   (root/'result.json').write_text(json.dumps({'video_references':['raw.mkv']}))
   (root/'traffic_spec').mkdir();(root/'traffic_spec/trace.json').write_text(json.dumps({'scenes':[{'structures':[]}]}))
   case={'case_id':'C999999-preview','target_law_id':'fixture'}
   data={'review_source_video_frames':[1,2],'review_source_window_s':[.1,.15],
         'preview_source_video_frames':[1,2],'preview_source_window_s':[.1,.15],
         'full_trace_frames':4,'full_recording_window_s':[.05,.2],'speed_evaluation':None,'trace_coverage':{'kind':'full_recording'}}
   with self.assertRaisesRegex(ValueError,'Primary review'):render(case,root,data)
   preview=render(case,root,data,preview=True)
   self.assertEqual(preview['frames'],2);self.assertEqual(preview['coverage_kind'],'preview')
   data.update(review_source_video_frames=[0,3],review_source_window_s=[.05,.2])
   primary=render(case,root,data)
   self.assertEqual(primary['frames'],4);self.assertEqual(primary['coverage_kind'],'full_delivered_trace')
   self.assertNotEqual(primary['video'],preview['video'])
   self.assertEqual(primary['trace_sha256'],hashlib.sha256((root/'traffic_spec/trace.json').read_bytes()).hexdigest())

 def test_full_frame_export_masks_obsolete_header_and_keeps_source(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'raw.mkv'
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=green:s=320x180:r=20','-frames:v','2','-c:v','ffv1',str(source)],check=True)
   before=hashlib.sha256(source.read_bytes()).hexdigest()
   trace=[{'frame':i+10,'time_s':(i+1)*.05,'speed_mps':2.0} for i in range(2)]
   mapping=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(trace)]
   for path,values in [('trace.jsonl',trace),('video_frames.jsonl',mapping)]:
    (root/path).write_text('\n'.join(json.dumps(r) for r in values)+'\n')
   receipt=convert(source,{'width':320,'height':180,'nb_read_frames':'2'})
   self.assertEqual(receipt['frames'],2);self.assertTrue(receipt['measured_speed_overlay'])
   self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
   probe=subprocess.run(['ffmpeg','-v','info','-i',receipt['video'],'-vf','crop=16:16:288:60,blackdetect=d=0:pix_th=0.02','-c:v','png','-f','null','-'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   self.assertIn('black_start:0',probe.stderr)
   self.assertEqual(convert(source,{'width':320,'height':180,'nb_read_frames':'2'})['sha256'],receipt['sha256'])


 def test_changed_expected_label_invalidates_review_cache(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'raw.mkv'
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=green:s=320x180:r=20','-frames:v','2','-c:v','ffv1',str(source)],check=True)
   trace=[{'frame':i+10,'time_s':(i+1)*.05,'speed_mps':2.0} for i in range(2)]
   mapping=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(trace)]
   for path,values in [('trace.jsonl',trace),('video_frames.jsonl',mapping)]:
    (root/path).write_text('\n'.join(json.dumps(r) for r in values)+'\n')
   (root/'result.json').write_text(json.dumps({'video_references':['raw.mkv']}))
   (root/'traffic_spec').mkdir();(root/'traffic_spec/trace.json').write_text(json.dumps({'scenes':[{'structures':[]}]}))
   case={'case_id':'C999999-fixture','target_law_id':'fixture'}
   record=dict(case,expected_label='compliant',judgment_sweep=False,scene_assumptions={},evidence={})
   (root/'expected_label.json').write_text(json.dumps(record))
   data={'review_source_video_frames':[0,1],'full_trace_frames':2,'full_recording_window_s':[.05,.1],'speed_evaluation':None,'review_source_window_s':[.05,.1],'trace_coverage':{'kind':'full_recording'}}
   first=render(case,root,data)
   record['expected_label']='non_compliant';(root/'expected_label.json').write_text(json.dumps(record))
   second=render(case,root,data)
   self.assertNotEqual(first['scenario_overlay_sha256'],second['scenario_overlay_sha256'])
   self.assertNotEqual(first['video_sha256'],second['video_sha256'])
   self.assertNotEqual(first['recipe_sha256'],second['recipe_sha256'])

if __name__=='__main__':unittest.main()
