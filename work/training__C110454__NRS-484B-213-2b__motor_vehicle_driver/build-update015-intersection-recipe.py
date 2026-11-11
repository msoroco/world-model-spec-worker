"""Export current source-hashed 480-frame intersection diagnostic recipes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CAMERAS=(('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))
NAMES=('native_samples.jsonl','road_geometry.json','context.json',
       'video_frames.jsonl','body_history.jsonl','trace.jsonl',
       'capture/evidence.jsonl','capture/manifest.json',
       'capture/native/frames.jsonl','capture/recorder_info.txt','road.xodr')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load_script(name,alias):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build():
    fixture=load_script('saved-fixture-proof.py','c110454_update015_fixture')
    probe=load_script('probe-core-synthetic.py','c110454_update015_core')
    outputs=[]
    for suffix in ('reference','contrast'):
        with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c110454-recipe-source-') as temp:
            source=Path(temp)/'attempt'
            fixture.make_base(source,suffix,480)
            probe.enrich(source)
            files={name:(source/name).read_text() for name in NAMES}
            files['acquisition-provenance.json']=json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n'
            sample=rows(source/'native_samples.jsonl')
            evidence=rows(source/'capture/evidence.jsonl')
            frames=rows(source/'capture/native/frames.jsonl')
            if len(sample)!=len(evidence) or len(sample)!=len(frames) or len(sample)!=480:
                raise ValueError('Synthetic source counts differ')
            if not all(s.get('speed_provenance')=='synthetic_native_sample' for s in sample):
                raise ValueError('Synthetic speed provenance missing')
            graphs=[]
            for s,e,f in zip(sample,evidence,frames):
                x,y=s['native_center_xy_m']
                graphs.append({'path':'capture/native/'+f['base'],
                    'attributes':{'frame':f['frame'],'simulation_time_s':f['simulation_time'],
                                  'synthetic_diagnostic':True},
                    'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':107,
                         'vertex':[x,y,.5],'forward':[1,0,0],
                         'threedbbox':e['ego']['body_vertices_m']}}],
                    'edges':[]})
            videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,
                     'fps':20,'color':'black'} for name,width,height in CAMERAS]
            spec={'files':files,'graphs':graphs,'videos':videos}
            target=HERE/f'update015-{suffix}-diagnostic.json'
            target.write_text(json.dumps(spec,separators=(',',':'),allow_nan=False)+'\n')
            if target.stat().st_size>=2*1024*1024:
                raise ValueError('Diagnostic specification exceeds text return limit')
            relative=target.relative_to(REPO).as_posix();digest=sha(target)
            recipe={'format':'worker-fixture-recipe',
                    'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':digest}],
                    'generator':{'source':relative,'sha256':digest}}
            recipe_path=HERE/f'update015-{suffix}-recipe.json'
            recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
            outputs.append({'case_suffix':suffix,'frames':480,
                            'spec_bytes':target.stat().st_size,'spec_sha256':digest,
                            'recipe_sha256':sha(recipe_path)})
    (HERE/'update015-intersection-recipe-summary.json').write_text(json.dumps({
        'format':'c110454-update015-intersection-recipes','cases':outputs,
        'synthetic_diagnostic':True,'selected':False},indent=2)+'\n')
    print(json.dumps(outputs))


if __name__=='__main__':
    build()
