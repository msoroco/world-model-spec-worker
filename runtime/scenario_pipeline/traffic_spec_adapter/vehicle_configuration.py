"""Opt-in source-qualified single-chassis classification; no generic absence."""
import hashlib,json,math

METHOD='verified_single_chassis_configuration_v2'
# Reviewed component/physics source: one Vehicle_Base and four wheel-to-base
# constraints, no second chassis; derived family changes only lateral scale.
STOCK=('9639af16f5bc4b1b956fd6d4db616d82b6dcbb9dae9b5c2d6b9fe980adb69a10',
       'd424d429ac33acbea02ead7788c491723c2d0d8287d729f9d48ed3e43fe268ce')
DERIVED_UASSET='6fb64e6479012de5de5a54370713a2761a8c8883254d970fea70270a773f81aa'
DERIVED_UEXP={'40a5c598bf2cfec74235a89b160a15a39d69c7ca074f8c12889961f70a03cbd7',
 '756f344c742c970d74e9f5480d1b752c7721e5ad5d4a1bdcf7c947878fe9a424',
 'd955e5ee71bb99fe47a5f98d466a9d6c9973b89fe480d839d4c239ccc9e3abf1'}

def digest(path):
 h=hashlib.sha256()
 with path.open('rb')as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()

def load_single_chassis(evidence):
 """Capability is conditional; this separately proves one record's coverage."""
 path=evidence.path('single_chassis_source.json')
 if path is None:return None
 proof=json.loads(path.read_text())
 if proof.get('schema')!=METHOD:raise ValueError('Unsupported single-chassis source contract')
 required={'trace.jsonl','runner.py','config.json','capture/manifest.json','single_chassis_frames.jsonl'}
 if not required<=set(proof.get('evidence',{})):raise ValueError('Incomplete single-chassis original sources')
 for name,expected in proof['evidence'].items():
  source=evidence.path(name)
  if source is None or digest(source)!=expected:raise ValueError('Single-chassis original source hash differs')
 manifest=json.loads(evidence.path('capture/manifest.json').read_text())
 if manifest.get('acquisition')!='original_live_run':raise ValueError('Single-chassis source must be original live evidence')
 config=json.loads(evidence.path('config.json').read_text())
 models=proof.get('models',{});qualified={}
 for blueprint,model in models.items():
  files=model.get('files',{});pair=[]
  for extension in('uasset','uexp'):
   entry=files.get(extension,{})
   source=evidence.path(entry.get('path',''))
   if source is None or digest(source)!=entry.get('sha256'):raise ValueError('Single-chassis asset hash differs')
   pair.append(entry['sha256'])
  if not ((blueprint=='vehicle.carlamotors.carlacola'and tuple(pair)==STOCK)or
          (blueprint=='vehicle.carlamotors.european_hgv'and pair[0]==DERIVED_UASSET and pair[1]in DERIVED_UEXP)):
   raise ValueError('Unqualified single-chassis model topology')
  qualified[blueprint]=tuple(pair)
  if blueprint=='vehicle.carlamotors.european_hgv':
   expected={'BP_European_HGV.uasset':pair[0],'BP_European_HGV.uexp':pair[1]}
   if config.get('native_asset_configuration',{}).get('candidate_file_hashes')!=expected:
    raise ValueError('Configured original asset differs from qualified source')
   name='verified_native_asset_configuration.json'
   if name not in proof['evidence']:raise ValueError('Missing original loaded asset binding')
   metadata=json.loads(evidence.path(name).read_text())
   if metadata.get('frozen')!=config.get('native_asset_configuration'):
    raise ValueError('Original loaded asset scope differs')
   overlay=metadata.get('actual_owned_overlay',{}).get('files',{})
   if {p.rsplit('/',1)[-1]:v.get('candidate_sha256')for p,v in overlay.items()}!=expected:
    raise ValueError('Original owned runtime asset hashes differ')
 if not qualified:raise ValueError('No qualified single-chassis model')
 frames={};seen=set();prior=None;rows=evidence.rows('single_chassis_frames.jsonl');original_rows=evidence.rows('trace.jsonl')
 if len(rows)!=len(original_rows):raise ValueError('Normalized/source frame coverage differs')
 for row,original in zip(rows,original_rows):
  if row.get('original_trace_row_sha256')!=hashlib.sha256(json.dumps(original,sort_keys=True,separators=(',',':')).encode()).hexdigest():raise ValueError('Normalized/source frame hash differs')
  frame=row.get('frame');stamp=row.get('time_s');native=row.get('following_native',{})
  cfg=native.get('native_vehicle_configuration')
  if not isinstance(cfg,dict):raise ValueError('Original frame lacks single-chassis configuration')
  if(type(frame)is not int or type(stamp)not in(int,float)or not math.isfinite(stamp)or
     cfg.get('schema')!='single-chassis-configuration-v1'or
     any(x.get('frame')!=frame or x.get('time_s')!=stamp for x in(native,cfg))or
     frame in seen or(prior is not None and frame!=prior+1)):
   raise ValueError('Single-chassis frame/time source join differs')
  seen.add(frame);prior=frame
  if cfg.get('native_asset_configuration')!=config.get('native_asset_configuration'):
   raise ValueError('Per-frame source asset scope differs from configuration')
  validate_source_identity(row,original)
  inventory=native.get('native_actor_inventory',[]);hier=cfg.get('actor_hierarchy',[]);vehicles=cfg.get('vehicles',[])
  im={a['id']:a['type']for a in inventory};hm={a['actor_id']:a for a in hier};vm={a['actor_id']:a for a in vehicles}
  if len(im)!=len(inventory)or len(hm)!=len(hier)or len(vm)!=len(vehicles):raise ValueError('Duplicate single-chassis source identity')
  if im!={i:a['type_id']for i,a in hm.items()}:raise ValueError('Incomplete single-chassis actor hierarchy')
  actors=[native.get('ego',{}),native.get('apparatus',{})]+native.get('extra_traffic',[])
  pm={a.get('actor_id'):a for a in actors};physical={i:t for i,t in im.items()if t.startswith(('vehicle.','walker.'))}
  if len(pm)!=len(actors)or set(pm)!=set(physical)or any(pm[i].get('blueprint')!=t for i,t in physical.items()):
   raise ValueError('Incomplete single-chassis participant inventory')
  for aid,a in hm.items():
   parent=a.get('parent_actor_id')
   if parent is not None and parent not in hm:raise ValueError('Unresolved single-chassis attachment parent')
  accepted={}
  for aid,a in vm.items():
   blueprint=a.get('blueprint')
   if aid not in physical or blueprint!=physical[aid]:raise ValueError('Single-chassis configuration actor identity differs')
   if blueprint not in qualified:continue
   if(a.get('parent_actor_id')is not None or hm[aid].get('parent_actor_id')is not None or
      a.get('configuration')!='single_rigid_goods_truck'):
    raise ValueError('Single-chassis configuration conflicts with original source')
   if any(child.get('parent_actor_id')==aid and not child['type_id'].startswith('sensor.')for child in hier):
    raise ValueError('Additional attached physical unit')
   accepted[aid]=blueprint
  targets={native.get('ego',{}).get('actor_id'),native.get('apparatus',{}).get('actor_id')}
  if not targets<=set(accepted):raise ValueError('Original frame lost required qualified vehicle configuration')
  key=round(stamp*1000)
  if key in frames:raise ValueError('Duplicate single-chassis timestamp')
  frames[key]={'frame':frame,'actors':accepted}
 if len(rows)!=proof.get('frames')or len(rows)!=manifest.get('frames')or not rows:
  raise ValueError('Incomplete single-chassis recording period')
 return {'method':METHOD,'source_sha256':digest(path),'frames':frames,'complete_frames':len(frames)}

def project_single_chassis(scene,scope,packet):
 if scope is None:return 0
 observed=scope['frames'].get(scene['t'])
 if observed is None or observed['frame']!=packet.get('native_frame'):
  raise ValueError('Single-chassis trace/source frame differs')
 changed=0
 for user in scene.get('users',[]):
  if user['track']not in observed['actors']:continue
  if {'trailer','vehicle_combination'}&set(user.get('classes')or[]):raise ValueError('Single-chassis class conflicts with source')
  # classes=None means no class inventory, so removing a mask cannot create
  # a readable negative; retain unknown instead of claiming completion.
  if user.get('classes')is None:continue
  unknown=user.get('unobserved_classes',[])
  if {'trailer','vehicle_combination'}&set(unknown):
   user['unobserved_classes']=[x for x in unknown if x not in {'trailer','vehicle_combination'}];changed+=1
 return changed


def validate_source_identity(row,original):
 """Exact identity joins to immutable originals, never old-schema admission."""
 native=row['following_native'];raw=original['following_native']
 cfg=native['native_vehicle_configuration'];source=raw['native_vehicle_configuration']
 if any(row.get(k)!=original.get(k)or cfg.get(k)!=source.get(k)for k in ('frame','time_s')):
  raise ValueError('Normalized/source frame identity differs')
 if native.get('native_actor_inventory')!=raw.get('native_actor_inventory')or cfg.get('actor_hierarchy')!=source.get('actor_hierarchy'):
  raise ValueError('Normalized/source hierarchy differs')
 keys=('actor_id','blueprint','parent_actor_id','configuration')
 if [[a.get(k)for k in keys]for a in cfg.get('vehicles',[])]!=[[a.get(k)for k in keys]for a in source.get('vehicles',[])]:
  raise ValueError('Normalized/source vehicle configuration differs')
 for key in ('ego','apparatus'):
  if any(native.get(key,{}).get(k)!=raw.get(key,{}).get(k)for k in ('actor_id','blueprint')):raise ValueError('Normalized/source participant differs')
 if [[a.get(k)for k in ('actor_id','blueprint')]for a in native.get('extra_traffic',[])]!=[[a.get(k)for k in ('actor_id','blueprint')]for a in raw.get('extra_traffic',[])]:raise ValueError('Normalized/source extra participant differs')
