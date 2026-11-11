"""Export source-hashed 480-frame right-turn diagnostic recipes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIXES=('reference','contrast')
CAMERAS=(('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))
NAMES=('native_samples.jsonl','road_geometry.json','context.json',
       'video_frames.jsonl','body_history.jsonl','trace.jsonl',
       'capture/evidence.jsonl','capture/manifest.json',
       'capture/native/frames.jsonl','capture/recorder_info.txt','road.xodr')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load_script(name,alias):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build():
    fixture=load_script('saved-fixture-proof.py','c110919_fixture')
    from sys import path
    path.insert(0,str(HERE/'native'))
    from geometry import open_drive
    outputs=[]
    for suffix in SUFFIXES:
        with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110919-recipe-') as temp:
            source=Path(temp)/'attempt'
            fixture.make_attempt(source,suffix,full_resolution=False)
            trace=rows(source/'trace.jsonl')
            evidence=rows(source/'capture/evidence.jsonl')
            samples=rows(source/'native_samples.jsonl')
            if len(trace)!=len(evidence) or len(trace)!=len(samples) or len(trace)!=480:
                raise ValueError('Right-turn source counts differ')
            frames=[];graphs=[]
            for t,e,s in zip(trace,evidence,samples):
                frame=t['frame'];time=t['time_s'];x,y=s['native_center_xy_m']
                frames.append({'frame':frame,'simulation_time':time,'time_s':time,
                    'base':f'graphs/base/{frame:08d}.pkl',
                    'abstract':f'graphs/abstract/{frame:08d}.pkl',
                    'synthetic_diagnostic':True})
                graphs.append({'path':f'capture/native/graphs/base/{frame:08d}.pkl',
                    'attributes':{'frame':frame,'simulation_time_s':time,
                                  'synthetic_diagnostic':True},
                    'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':107,
                         'vertex':[x,y,.5],'forward':[1,0,0],
                         'threedbbox':e['ego']['body_vertices_m']}}],
                    'edges':[]})
            (source/'capture/native').mkdir(parents=True,exist_ok=True)
            (source/'capture/native/frames.jsonl').write_text(''.join(
                json.dumps(row)+'\n' for row in frames))
            (source/'road.xodr').write_text(open_drive())
            manifest=json.loads((source/'capture/manifest.json').read_text())
            manifest['sources']={'road.xodr':sha(source/'road.xodr'),
                                 'trace.jsonl':sha(source/'trace.jsonl')}
            (source/'capture/manifest.json').write_text(json.dumps(manifest))
            files={name:(source/name).read_text() for name in NAMES}
            files['acquisition-provenance.json']=json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n'
            videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,
                     'fps':20,'color':'black'} for name,width,height in CAMERAS]
            target=HERE/f'update015-{suffix}-diagnostic.json'
            target.write_text(json.dumps({'files':files,'graphs':graphs,'videos':videos},
                                         separators=(',',':'),allow_nan=False)+'\n')
            if target.stat().st_size>=2*1024*1024:
                raise ValueError('Right-turn diagnostic exceeds text return limit')
            relative=target.relative_to(REPO).as_posix();digest=sha(target)
            recipe={'format':'worker-fixture-recipe',
                    'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':digest}],
                    'generator':{'source':relative,'sha256':digest}}
            recipe_path=HERE/f'update015-{suffix}-recipe.json'
            recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
            outputs.append({'case_suffix':suffix,'frames':480,
                            'spec_bytes':target.stat().st_size,'spec_sha256':digest,
                            'recipe_sha256':sha(recipe_path)})
    (HERE/'update015-recipe-summary.json').write_text(json.dumps({
        'format':'c110919-update015-recipes','cases':outputs,
        'synthetic_diagnostic':True,'selected':False},indent=2)+'\n')
    print(json.dumps(outputs))


if __name__=='__main__':build()
