"""Original-tick RGB encoding and mandatory measured channel capture."""
import json,pathlib,queue,subprocess,sys

class Resources:
 def __init__(self):self.callbacks=[]
 def own(self,callback):self.callbacks.append(callback)
 def close(self):
  errors=[]
  for callback in reversed(self.callbacks):
   try:callback()
   except BaseException as e:errors.append(type(e).__name__+': '+str(e))
  self.callbacks=[];return errors

class Recording:
 def __init__(self,client,ego,output,case_id,description,cameras,required_atoms=()):
  self.output=pathlib.Path(output);self.output.mkdir(parents=True,exist_ok=True);self.resources=Resources();self.channels={};self.evidence=[];self.cameras=[];self.encoders=[];self.frames=0;self.closed=False;self.close_errors=[]
  self.description=description
  try:
   import carla
   from pipeline_capture import PipelineCapture
   self.capture=PipelineCapture(client,ego,self.output,case_id,required_observations=required_atoms);self.resources.own(lambda:self.capture.close(confirmed=not self.close_errors))
   self.evidence_reader=(self.output/'capture/evidence.jsonl').open();self.resources.own(self.evidence_reader.close);self.last_evidence=None
   for idx,pose in enumerate(cameras):
    bp=client.get_world().get_blueprint_library().find('sensor.camera.rgb');width=pose.get('width',1920 if idx==0 else 1280);height=pose.get('height',1080 if idx==0 else 720)
    bp.set_attribute('image_size_x',str(width));bp.set_attribute('image_size_y',str(height));bp.set_attribute('sensor_tick','0.0')
    loc=pose.get('location',[pose.get('x',-8),pose.get('y',0),pose.get('z',4)])
    camera=client.get_world().spawn_actor(bp,carla.Transform(carla.Location(*loc),carla.Rotation(pitch=pose.get('pitch',-15))),attach_to=ego)
    self.resources.own(camera.destroy);self.resources.own(camera.stop);q=queue.Queue();camera.listen(q.put);self.cameras.append(q)
    path=self.output/('camera-'+str(idx)+'.webm')
    process=subprocess.Popen(['ffmpeg','-v','error','-n','-f','rawvideo','-pixel_format','bgra','-video_size',str(width)+'x'+str(height),'-framerate','20','-i','pipe:0','-an','-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-pix_fmt','yuv420p',str(path)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    self.encoders.append(process);self.resources.own(lambda p=process:self._finish_encoder(p))
   self.frame_map=(self.output/'video_frame_map.jsonl').open('x');self.resources.own(self.frame_map.close)
   (self.output/'channels').mkdir(exist_ok=False)
   for c in description['channels']:
    name=c['name'];p=self.output/'channels'/(name+'.jsonl');f=p.open('x');self.channels[name]=f;self.resources.own(f.close);self.evidence.append(dict(name=name,unit=c['unit'],reference='channels/'+name+'.jsonl'))
  except BaseException:self.close();raise
 def _finish_encoder(self,process):
  if process.stdin and not process.stdin.closed:process.stdin.close()
  error=process.stderr.read();code=process.wait(timeout=90)
  if code:raise RuntimeError('Video encoder failed: '+error.decode(errors='replace'))
 def tick(self,frame,time_s,observations,extra=None):
  row=self.capture.capture(frame,time_s,extra=extra)
  event=self.evidence_reader.readline()
  if not event:raise RuntimeError('Missing original captured observation packet')
  self.last_evidence=json.loads(event)
  if self.last_evidence['original_frame']!=frame:raise RuntimeError('Original evidence frame mismatch')
  if callable(observations):observations=observations(row,self.last_evidence)
  missing=[name for name in self.channels if observations.get(name) is None]
  if missing:raise ValueError('Mandatory observation unavailable: '+','.join(missing))
  for name,f in self.channels.items():f.write(json.dumps(dict(time_s=time_s,value=observations[name]))+'\n')
  for q,encoder in zip(self.cameras,self.encoders):
   image=q.get(timeout=30)
   while image.frame<frame:image=q.get(timeout=30)
   if image.frame!=frame:raise RuntimeError('Original camera timestamp mismatch')
   encoder.stdin.write(bytes(image.raw_data))
  self.frame_map.write(json.dumps(dict(video_frame=self.frames,carla_frame=frame,time_s=time_s))+'\n');self.frames+=1
  return row
 def close(self):
  if not self.closed:self.closed=True;self.close_errors+=self.resources.close()
  return self.close_errors
 def result_fields(self):
  return dict(trace_reference='trace.jsonl',video_frame_map_reference='video_frame_map.jsonl',video_references=['camera-'+str(i)+'.webm' for i in range(len(self.cameras))],recording_evidence=self.evidence,recording_description=self.description)
