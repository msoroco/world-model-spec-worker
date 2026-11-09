"""Curated existing capability implementations, exported from retained evidence."""
import pathlib,json,sqlite3,re,shutil
from pathlib import Path
from .common import read,write,sha

def export(project,root,destination):
    root=Path(root);out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect((root/'state/demo-thirteen-complete-20261010.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    entries=[]
    for label,cell,law in [('crest','C104496','NRS-484B-407'),('heavy_vehicle','C102372','NRS-484B-127-2')]:
     member=next(m for m in read(root/'sets/demo-train/selection.json')['members'] if m['cell_id']==cell and m['law_id']==law)
     metadata=read(root/'recordings'/member['recording_id']/'metadata.json');record=metadata.get('published_record',{});provenance=record.get('provenance',{})
     jid=provenance.get('completion_binding',{}).get('job_id')
     if jid is None:
      jid=int(re.search(r'(\d+)-attempt',record['attempt_id']).group(1))
     row=con.execute("select j.artifact_id from dependencies d join jobs j on j.id=d.dependency_id where d.job_id=? and j.stage='construction'",(jid,)).fetchone()
     construction=json.loads(con.execute('select payload from artifacts where id=?',row).fetchone()[0])
     d=out/label;d.mkdir(exist_ok=True)
     for f in construction['files']:
      path=d/f['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(f['content'])
     write(d/'provenance.json',{'recording_id':member['recording_id'],'source_job':jid,'source_artifact':row[0],'scope':'Historical successful construction, not current-cell geometry, measurements or accepted reuse','actor':member['actor']})
     alltext='\n'.join(f['content'] for f in construction['files'])
     entries.append({'name':label,'reference':label+'/provenance.json','assets_mentioned':sorted(set(re.findall(r'(?:vehicle|static\.prop|traffic)\.[a-zA-Z0-9_.]+',alltext))),'limitations':'Requery inventory, dimensions, native map connectivity, controller behavior and visibility for each new instance'})
    for filename in ('check_indicator_rendering.py','verify_recorded_indicators.py'):
     shutil.copyfile(Path(project)/'scenario_pipeline'/filename,out/filename)
    entries += [{'name':'indicator','reference':'verify_recorded_indicators.py','capture_reference':'check_indicator_rendering.py','limitations':'Historical left Tesla lamp/view ROI; derive and calibrate new right-lamp ROI rather than inheriting it. Source uses actual RGB and API samples separately.'},
     {'name':'stop_sign_and_boundaries','reference':'../../../examples/intersection/original-construction.json','limitations':'Marked-line stop reference; do not transfer to yield-sign or missing-crosswalk branch unchanged.'},
     {'name':'divider_opening','reference':'../../../migration-candidates/index.json','limitations':'Prior worker routes are untrusted candidates. Collidable barriers do not prove a traversable median is impossible.'}]
    environmental=root/'recordings/19c5f6d56b83f152478ab36ff9d1bd345c41cdc7a0945f866c4070fab93acee9/evidence'
    if environmental.exists():
     d=out/'environment';d.mkdir(exist_ok=True)
     source_hashes={}
     for name in ('runner.py','config.json','scene.xodr','native_following_capture.py','scene_model.py','footprint_gap.py','cleanup.py'):
      source=environmental/name
      if source.is_file():shutil.copyfile(source,d/name);source_hashes[name]=sha(source)
     write(d/'provenance.json',{'recording_id':environmental.parent.name,'original_environment_capture_sha256':sha(environmental/'environment_capture.py'),'source_hashes':source_hashes,'portable_helper':'../../scenario_pipeline/worker_exchange/environment_acquisition.py','scope':'Historical acquisition method, not a current-case measurement or runnable unchanged configuration'})
     entries.append({'name':'environment','reference':'environment/provenance.json','limitations':'surface_receipt encodes the original dry asphalt geometry and absence-of-ice synthetic authoring. Adapt dimensions/material inventory explicitly for another construction. Recalibrate target/scene; never infer ice absence from weather. Original asset paths are provenance, not portable execution locators.'})
    write(out/'catalogue.json',{'entries':entries,'policy':'Reuse code and discovery methods, never historic measurements as new-cell evidence. Administrative status needs a source or explicit synthetic assumption; not rendered pixels.'})
    print('Capability references',len(entries))
    con.close()
    return entries
