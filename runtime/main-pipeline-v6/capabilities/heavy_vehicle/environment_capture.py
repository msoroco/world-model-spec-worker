"""Native RGB/instance contrast-range instrument; no legal visibility standard.

A finite sampled, target/camera-specific optical observation, not geometric LOS.
Instance segmentation identifies target pixels; only RGB provides contrast.
"""
import hashlib,json,math,queue
from pathlib import Path
from following_controller import elevation

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fields(obj):return {k:getattr(obj,k) for k in dir(obj) if not k.startswith('_') and isinstance(getattr(obj,k),(bool,int,float,str,type(None)))}
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def xyz(p):return [p.x,p.y,p.z]
def get_image(q,frame):
 im=q.get(timeout=45)
 while im.frame<frame:im=q.get(timeout=45)
 if im.frame!=frame:raise RuntimeError('Calibration sensor frame mismatch')
 return im

def calibrate(world,target,out,owned,distances=(10,25,50,100,200,400)):
 import carla,numpy as np
 from PIL import Image
 def binary_dilation(mask,iterations):
  result=mask.copy()
  for _ in range(iterations):
   before=result.copy();result[1:,:]|=before[:-1,:];result[:-1,:]|=before[1:,:];result[:,1:]|=before[:,:-1];result[:,:-1]|=before[:,1:]
  return result
 out=Path(out);root=out/'environment-calibration';root.mkdir(exist_ok=False)
 sensors={};weather=fields(world.get_weather());tr=target.get_transform();centre=tr.transform(target.bounding_box.location)
 for key,typ in [('rgb','sensor.camera.rgb'),('instance','sensor.camera.instance_segmentation')]:
  bp=world.get_blueprint_library().find(typ)
  for k,v in [('image_size_x','1920'),('image_size_y','1080'),('fov','60'),('sensor_tick','0')]:bp.set_attribute(k,v)
  if key=='rgb':
   for k,v in [('enable_postprocess_effects','true'),('motion_blur_intensity','0')]:
    if bp.has_attribute(k):bp.set_attribute(k,v)
  a=world.spawn_actor(bp,carla.Transform(carla.Location(x=centre.x-25,y=centre.y,z=elevation(centre.x-25)+1.4)));owned.append(a);q=queue.Queue();a.listen(q.put);sensors[key]=(a,q)
 records=[]
 try:
  for distance in distances:
   eye=carla.Location(x=centre.x-distance,y=centre.y,z=elevation(centre.x-distance)+1.4);delta=centre-eye
   rotation=carla.Rotation(pitch=math.degrees(math.atan2(delta.z,math.hypot(delta.x,delta.y))),yaw=math.degrees(math.atan2(delta.y,delta.x)))
   for sensor,q in sensors.values():sensor.set_transform(carla.Transform(eye,rotation))
   for _ in range(12):frame=world.tick()
   images={k:get_image(q,frame) for k,(_,q) in sensors.items()}
   rgb=np.frombuffer(images['rgb'].raw_data,dtype=np.uint8).reshape(1080,1920,4)[:,:,:3][:,:,::-1].copy()
   ins=np.frombuffer(images['instance'].raw_data,dtype=np.uint8).reshape(1080,1920,4)[:,:,:3][:,:,::-1].copy()
   # G/B form an instance code. Record both encoding and semantic tag. The
   # target is the only centred car; exact code comes from its centre pixel.
   window=ins[480:600,900:1020];codes=window[:,:,1].astype(np.uint16)*256+window[:,:,2].astype(np.uint16)
   candidates=[]
   for tag in (14,10):
    values=window[:,:,0]==tag
    if values.any():
     u,c=np.unique(codes[values],return_counts=True);candidates.extend((int(n),int(code),tag) for code,n in zip(u,c) if code)
   if not candidates:raise RuntimeError('Native calibration target mask missing')
   _,code,tag=max(candidates);all_codes=ins[:,:,1].astype(np.uint16)*256+ins[:,:,2].astype(np.uint16)
   mask=(ins[:,:,0]==tag)&(all_codes==code);ys,xs=np.where(mask)
   if len(xs)<4:raise RuntimeError('Target below four sensor pixels; censored measurement unsupported')
   # Local RGB background annulus; segmentation is never visibility evidence.
   ring=binary_dilation(mask,iterations=5)&~binary_dilation(mask,iterations=2)
   luminance=rgb.astype(float)@np.array([.2126,.7152,.0722]);background=float(np.median(luminance[ring]));target_lum=float(np.median(luminance[mask]));contrast=abs(target_lum-background)/max(1.,background)
   sources={}
   for key,array in [('rgb',rgb),('instance',ins)]:
    path=root/('%s-%04d.png'%(key,distance));Image.fromarray(array).save(path);sources[key]={'path':str(path.relative_to(out)),'sha256':sha(path)}
   records.append(dict(distance_m=float(eye.distance(centre)),longitudinal_range_m=distance,frame=frame,observer_m=xyz(eye),target_centre_m=xyz(centre),target_actor_id=target.id,instance_code=code,semantic_tag=tag,target_pixels=len(xs),target_median_luminance=target_lum,background_median_luminance=background,weber_contrast=contrast,contrast_detected=contrast>=.05,mask_bbox_px=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],**sources))
  positives=[r for r in records if r['contrast_detected']]
  if not positives:raise RuntimeError('No sampled distance meets the instrument contrast convention')
  # First sustained loss brackets the sampled instrument range; retain all data.
  last=records[0];first_failure=None
  for r in records:
   if not r['contrast_detected']:first_failure=r;break
   last=r
  if not records[0]['contrast_detected']:raise RuntimeError('Near target lacks contrast; cannot calibrate')
  result={'schema':'rendered-target-contrast-range-v1','passed':True,'method':'Native1920x1080 RGB60deg horizontal FOV, native default exposure/tone mapping camera; median target luminance versus2..5pixel background annulus, absolute Weber contrast>=0.05. Engineering instrument only; no legal or human perception threshold. Instance camera supplies mask only.','visibility_m':last['longitudinal_range_m'],'distance_kind':'sampled_bracket' if first_failure else 'sampled_lower_bound','upper_bracket_m':first_failure['longitudinal_range_m'] if first_failure else None,'weather':weather,'target':{'actor_id':target.id,'blueprint':target.type_id,'transform':{'location_m':xyz(tr.location),'rotation_deg':fields(tr.rotation)},'body_vertices_m':[xyz(x) for x in target.bounding_box.get_world_vertices(tr)]},'samples':records,'uncertainty':'Finite range grid10/25/50/100/200/400m; 8-bit rendered RGB with native exposure/tone mapping, target-specific appearance/background,4pixel minimum. Scalar is the last passing sampled bound, not an exact atmospheric cutoff or roadway sight distance. No extrapolation. Fixed atmosphere/lighting is checked every recorded tick; scene is authored homogeneous.','source_documentation':['https://carla.readthedocs.io/en/latest/tuto_G_instance_segmentation_sensor/','https://carla.readthedocs.io/en/0.9.15/ref_sensors/'],'camera_attributes':{k:dict(a.attributes) for k,(a,q) in sensors.items()},'instrumentation_sha256':sha(__file__),'crest_transfer':{'eye_height_above_authored_road_m':1.4,'target_downstream_constant_grade':True,'minimum_observer_station_m':centre.x-max(distances),'minimum_supported_constant_grade_station_m':850,'no_crest_in_optical_instrument_path':True}}
  write(out/'environment_calibration.json',result);return result
 finally:
  for sensor,q in sensors.values():
   sensor.stop();sensor.destroy();owned.remove(sensor)

def surface_receipt(world,mapping,out,construction,assets):
 result={'schema':'authored-native-road-surface-v1','authorship':'Explicit synthetic construction of the unchanged native generated procedural/default crest mesh with no authored ice/snow layers or ice/snow actors. Not inferred from precipitation or wetness.', 'ice_or_snow':False,'map_sha256':sha(Path(out)/'road.xodr'),'authored_map_sha256':sha(construction),'source_assets':[{'path':str(p),'sha256':sha(p)} for p in assets],'native_map_name':mapping.name,'native_actor_inventory':[{'id':a.id,'type':a.type_id} for a in world.get_actors()],'surface_condition':'Native generated procedural/default road; exact native weather and per-vehicle wheel/trigger physics retained separately','highway_width_m':24.,'roadway_width_m':24.,'lane_width_m':12.,'shoulder_width_each_m':0.,'boundary_reference':'Native road1 driving lanes -1 and+1, each12m; no shoulder lane substituted','limitations':['Native wheel tire_friction is an engine setting, not a measured real-world friction coefficient.','Snow/ice absence is an explicit authored source fact; actual native map/assets and RGB remain retained.']}
 write(Path(out)/'surface_provenance.json',result);return result
