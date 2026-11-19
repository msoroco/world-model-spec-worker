"""Author explicit flat grade in all selected OpenDRIVE constructions and recipes."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def flat(text):
 root=ET.fromstring(text)
 roads=root.findall('road')
 if len(roads)!=4 or any(r.find('elevationProfile') is not None for r in roads):raise ValueError('Expected four roads without elevation records')
 for road in roads:
  profile=ET.Element('elevationProfile')
  ET.SubElement(profile,'elevation',{'s':'0','a':'0','b':'0','c':'0','d':'0'})
  plan=road.find('planView');road.insert(list(road).index(plan)+1,profile)
 return ET.tostring(root,encoding='unicode')
def main():
 mp=HERE/'execution-manifest.json';m=json.loads(mp.read_text());old_road=None;new_road=None
 for e in m['cases']:
  suffix=e['case_id'].removeprefix(HERE.name+'__')
  for c in [e,*e['candidates']]:
   name=c.get('id','primary');old=json.loads((HERE/c['construction']).read_text())
   roads={x['path']:x['content'] for x in old['files'] if x['path'].endswith('.xodr')}
   if roads.get('road.xodr')!=roads.get('right-exit-road.xodr'):raise ValueError('Road copies differ')
   source=roads['road.xodr'];revised=flat(source)
   if old_road is None:old_road=hashlib.sha256(source.encode()).hexdigest();new_road=hashlib.sha256(revised.encode()).hexdigest()
   if hashlib.sha256(source.encode()).hexdigest()!=old_road or hashlib.sha256(revised.encode()).hexdigest()!=new_road:raise ValueError('Candidate roads differ')
   for f in old['files']:
    if f['path'] in roads:f['content']=revised
    elif f['path']=='config.json':
     if old_road not in f['content']:raise ValueError('Config lacks pinned road hash')
     f['content']=f['content'].replace(old_road,new_road)
   dest=HERE/'native/package-current-input-v3'/suffix/name/'construction.json'
   put(dest,old);c['construction']=dest.relative_to(HERE).as_posix();c['construction_sha256']=sha(dest)
  recipe_path=ROOT/e['fixture_recipe'];recipe=json.loads(recipe_path.read_text());spec_path=ROOT/recipe['generator']['source'];spec=json.loads(spec_path.read_text());capture=json.loads(spec['files']['capture/manifest.json']);
  if capture['sources']['road.xodr']!=old_road:raise ValueError('Diagnostic capture road differs')
  capture['sources']['road.xodr']=new_road;spec['files']['capture/manifest.json']=json.dumps(capture,indent=2)+'\n'
  new_spec=HERE/f'update601-{suffix}-diagnostic.json';put(new_spec,spec)
  recipe['generator']={'source':new_spec.relative_to(ROOT).as_posix(),'sha256':sha(new_spec)}
  new_recipe=HERE/f'update601-{suffix}-diagnostic-recipe.json';put(new_recipe,recipe);e['fixture_recipe']=new_recipe.relative_to(ROOT).as_posix()
 mp.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'cases':len(m['cases']),'candidates':8,'old_road_sha256':old_road,'flat_road_sha256':new_road,'manifest_sha256':sha(mp)}))
if __name__=='__main__':main()
