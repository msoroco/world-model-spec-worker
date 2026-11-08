"""Retain synthetic measured no-entry fallback triggers and negative checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
NAMES=('primary','fallback1','fallback2','fallback3')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def write_rows(path,values):path.write_text(''.join(json.dumps(v,sort_keys=True)+'\n' for v in values))

def main():
    manifest=json.loads((HERE/'draft-no-entry-execution-manifest.json').read_text())
    entry=manifest['cases'][0]
    root=HERE/'no-entry-trigger-sources';root.mkdir(exist_ok=True)
    baseline=rows(HERE/'no-entry-sources/native_samples.jsonl')
    outputs=[]
    for name in NAMES:
        ref=entry if name=='primary' else next(x for x in entry['candidates'] if x['id']==name)
        construction_path=HERE/ref['construction']
        if sha(construction_path)!=ref['construction_sha256']:
            raise ValueError('Exact no-entry trigger candidate hash differs')
        construction=json.loads(construction_path.read_text())
        code=next(x['content'] for x in construction['files'] if x['path']=='measure_no_entry_triggers.py')
        if hashlib.sha256(code.encode()).hexdigest()!=sha(HERE/'native/measure_no_entry_triggers.py'):
            raise ValueError('Exact candidate trigger meter differs')
        folder=root/name;folder.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(HERE/'no-entry-sources/road_geometry.json',folder/'road_geometry.json')
        samples=json.loads(json.dumps(baseline))
        if name=='fallback1':
            for index,row in enumerate(samples):
                shift=-10*(1-index/479)
                row['native_center_xy_m'][0]=round(row['native_center_xy_m'][0]+shift,6)
                row['native_body_xy_m']=[[round(x+shift,6),y] for x,y in row['native_body_xy_m']]
        if name=='fallback2':
            for row in samples:row['speed_mps']=1.8
        write_rows(folder/'native_samples.jsonl',samples)
        views=[]
        for row in samples:
            x=row['native_center_xy_m'][0]
            views.append({'native_frame':row['native_frame'],'time_s':row['time_s'],
                'body_visible':name=='fallback3' or not (-10<=x<=-6),
                'synthetic_diagnostic':True})
        write_rows(folder/'camera_visibility.jsonl',views)
        write(folder/'no-entry-trigger-sources.json',{
            'format':'c10052-no-entry-trigger-sources-v1','source_kind':'synthetic_cpu_fixture',
            'sha256':{p:sha(folder/p) for p in
                ('native_samples.jsonl','road_geometry.json','camera_visibility.jsonl')}})
        meter_path=folder/'measure_no_entry_triggers.py';meter_path.write_text(code)
        spec=importlib.util.spec_from_file_location('exact_no_entry_trigger_'+name,meter_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result=module.evaluate(folder)
        if name=='primary' and not all(result['fallback'+str(i)+'_trigger_measured'] for i in (1,2,3)):
            raise ValueError('Baseline no-entry triggers were not measured')
        if name!='primary' and result['fallback'+name[-1]+'_trigger_measured']:
            raise ValueError('Changed no-entry candidate did not clear its trigger')
        negative=folder/'negative';shutil.copytree(folder,negative,ignore=shutil.ignore_patterns('negative'))
        (negative/'camera_visibility.jsonl').write_bytes((negative/'camera_visibility.jsonl').read_bytes()+b' ')
        try:module.evaluate(negative)
        except ValueError as error:
            if 'No-entry trigger source hash differs' not in str(error):raise
        else:raise ValueError('Changed visibility source passed unexpectedly')
        outputs.append({'candidate':name,'construction_sha256':sha(construction_path),
            'meter_sha256':sha(meter_path),'source_sha256':sha(folder/'no-entry-trigger-sources.json'),
            'measurements':result,'changed_visibility_negative':True})
        shutil.rmtree(negative)
    proof={'format':'c10052-no-entry-trigger-proof-v1','passed':True,
        'manifest_sha256':sha(HERE/'draft-no-entry-execution-manifest.json'),
        'candidates':outputs,'source_kind':'synthetic_cpu_fixture',
        'physical_behavior_confirmed':False,'selected':False}
    write(HERE/'no-entry-trigger-proof.json',proof)
    return proof

if __name__=='__main__':
    proof=main()
    print(json.dumps({'passed':True,'candidates':[
        {'id':x['candidate'],'runway':x['measurements']['approach_runway_to_alley_m'],
         'peak_speed':x['measurements']['peak_approach_speed_mps'],
         'visibility_fraction':x['measurements']['reference_body_visibility_fraction']}
        for x in proof['candidates']]},indent=2))
