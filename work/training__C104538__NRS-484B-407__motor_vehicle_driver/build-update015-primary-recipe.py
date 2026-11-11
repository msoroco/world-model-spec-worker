"""Export one current textual 480-frame diagnostic from prior synthetic sources."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SOURCE_ROOT=REPO/'.runtime-work/c104538/joined-package-matrix-v6'
CAMERAS=(('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(source,name):
    return [json.loads(line) for line in (source/name).read_text().splitlines() if line.strip()]


def lines(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def build_one(suffix,candidate):
    source=SOURCE_ROOT/suffix/(candidate+'-fixture')
    traces=read_rows(source,'trace.jsonl')
    events=read_rows(source,'capture/evidence.jsonl')
    frames=read_rows(source,'capture/native/frames.jsonl')
    mapping=read_rows(source,'video_frames.jsonl')
    assert len(traces)==len(events)==len(frames)==len(mapping)==480
    trace_out=[];event_out=[];graph_out=[]
    for t,e,f,m in zip(traces,events,frames,mapping):
        assert t['frame']==e['original_frame']==f['frame']==m['native_frame']
        kept={key:t[key] for key in ('frame','time_s','position','position_m',
              'heading_deg','speed_mps','speed_mph','velocity_mps','control',
              'c104538_native','approaching_driver_views')}
        kept.update(synthetic_diagnostic=True,speed_provenance='synthetic_native_sample')
        trace_out.append(kept)
        event={'original_frame':e['original_frame'],
               'recording_time_s':e['recording_time_s'],
               'replay_frame':e['replay_frame'],
               'replay_simulation_time_s':e['replay_simulation_time_s'],
               'actor_id':e['actor_id'],
               'ego':{**e['ego'],'speed_provenance':'synthetic_native_sample'},
               'world':e['world'], 'synthetic_diagnostic':True}
        event_out.append(event)
        for name,width,height in CAMERAS:
            m.setdefault('original_rgb_sha256',{})[name]=sha(bytes(width*height*3))
        m['original_rgb_sha256']={name:m['original_rgb_sha256'][name]
                                  for name,_,_ in CAMERAS}
        graph_out.append({'path':'capture/native/'+f['base'],
            'attributes':{'frame':f['frame'],'simulation_time_s':f['simulation_time'],
                          'synthetic_diagnostic':True},
            'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':e['actor_id'],
                'vertex':e['ego']['position_m'],'forward':[1,0,0],
                'threedbbox':e['ego']['body_vertices_m']}}], 'edges':[]})
    files={name:(source/name).read_text() for name in (
        'native_body_history.jsonl','driver_eye_rays.jsonl',
        'native-construction-context.json','native_road_readback.xodr','road.xodr')}
    files.update({'trace.jsonl':lines(trace_out),
                  'capture/evidence.jsonl':lines(event_out),
                  'capture/native/frames.jsonl':lines(frames),
                  'video_frames.jsonl':lines(mapping),
                  'capture/recorder_info.txt':'Create 107: vehicle.tesla.model3\n',
                  'acquisition-provenance.json':json.dumps({
                      'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n'})
    manifest={'case_id':HERE.name+'__'+suffix,'frames':480,
              'extraction_confirmed':True,'synthetic_diagnostic':True,
              'sources':{'road.xodr':sha(files['road.xodr'].encode()),
                         'trace.jsonl':sha(files['trace.jsonl'].encode())}}
    files['capture/manifest.json']=json.dumps(manifest,separators=(',',':'))+'\n'
    videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,
             'fps':20,'color':'black'} for name,width,height in CAMERAS]
    spec={'files':files,'graphs':graph_out,'videos':videos}
    target=HERE/f'update015-{suffix}-{candidate}-diagnostic.json'
    target.write_text(json.dumps(spec,separators=(',',':'),allow_nan=False)+'\n')
    if target.stat().st_size>=2*1024*1024:
        raise ValueError('Diagnostic specification exceeds returned text limit: '+str(target.stat().st_size))
    relative=target.relative_to(REPO).as_posix();digest=sha(target.read_bytes())
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':digest}],
            'generator':{'source':relative,'sha256':digest}}
    output=HERE/f'update015-{suffix}-{candidate}-recipe.json'
    output.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case_suffix':suffix,'candidate_id':candidate,
            'spec_bytes':target.stat().st_size,'spec_sha256':digest,
            'recipe_sha256':sha(output.read_bytes()),'frames':480}


def build():
    rows=[]
    for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            item=build_one(suffix,candidate)
            rows.append(item)
            print(json.dumps(item),flush=True)
    base=json.loads((HERE/'draft-execution-manifest.json').read_text())
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        manifest=json.loads(json.dumps(base))
        for case in manifest['cases']:
            suffix=case['case_id'].rsplit('__',1)[1]
            case['fixture_recipe']=f'work/{HERE.name}/update015-{suffix}-{candidate}-recipe.json'
        (HERE/f'update015-manifest-{candidate}.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (HERE/'update015-recipe-summary.json').write_text(json.dumps({'format':'c104538-update015-exact-recipes',
        'cases':rows,'selected':False,'original_native_claimed':False},indent=2)+'\n')


if __name__=='__main__':
    build()
