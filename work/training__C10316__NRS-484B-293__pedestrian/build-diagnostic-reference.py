"""Export source-hashed, textual C10316 diagnostics from retained synthetic rows."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def build(suffix):
    if suffix not in ('reference','contrast'):
        raise ValueError('Only the two authored crosswalk cases may be exported')
    summary=json.loads((HERE/'saved-crosswalk-summary.json').read_text())
    source=Path(next(row['retained_positive'] for row in summary['records']
                     if row['case_suffix']==suffix))
    if not source.is_dir():
        raise ValueError('Retained synthetic source unavailable; regenerate saved fixture first')
    files={}
    for name in ('native_samples.jsonl','crosswalk-context.json','video_frames.jsonl',
                 'capture/native/frames.jsonl','capture/recorder_info.txt'):
        files[name]=(source/name).read_text()
    trace=[json.loads(s) for s in (source/'trace.jsonl').read_text().splitlines()]
    evidence=[json.loads(s) for s in (source/'capture/evidence.jsonl').read_text().splitlines()]
    native=[json.loads(s) for s in files['capture/native/frames.jsonl'].splitlines()]
    if len(trace)!=len(evidence) or len(trace)!=len(native) or len(trace)!=240:
        raise ValueError('Retained diagnostic frame counts differ')
    for row,event in zip(trace,evidence):
        row['synthetic_diagnostic']=True
        row['control']={'throttle':0,'brake':0,'hand_brake':False}
        event['synthetic_diagnostic']=True
        event['ego']['speed_provenance']='synthetic_native_sample'
    files['trace.jsonl']=lines(trace)
    files['capture/evidence.jsonl']=lines(evidence)
    manifest=json.loads((source/'capture/manifest.json').read_text())
    manifest['sources']['trace.jsonl']=sha_bytes(files['trace.jsonl'].encode())
    files['capture/manifest.json']=json.dumps(manifest,separators=(',',':'))+'\n'
    graphs=[]
    for frame,event in zip(native,evidence):
        graphs.append({'path':'capture/native/'+frame['base'],
                       'attributes':{'frame':frame['frame'],
                                     'simulation_time_s':frame['time_s'],
                                     'synthetic_diagnostic':True,
                                     'source':'C10316 synthetic saved pedestrian rows'},
                       'nodes':[{'id':'ego','attributes':{
                           'sem_class':'ego','entity_id':event['actor_id'],
                           'vertex':event['ego']['position_m'],
                           'forward':[1.0,0.0,0.0],
                           'threedbbox':event['ego']['body_vertices_m']}}],
                       'edges':[]})
    videos=[{'path':name+'.mkv','frames':240,'width':width,'height':height,
             'fps':20,'color':'black'} for name,width,height in (
                ('overview',1920,1080),('approach',1280,720),
                ('reference_corner',1280,720),('driver_reference',1280,720))]
    spec={'files':files,'graphs':graphs,'videos':videos}
    target=HERE/('diagnostic-'+suffix+'.json')
    target.write_text(json.dumps(spec,separators=(',',':'))+'\n')
    if target.stat().st_size>=2*1024*1024:
        raise ValueError('Diagnostic text exceeds worker file limit')
    source_path=target.relative_to(ROOT).as_posix()
    checksum=sha_bytes(target.read_bytes())
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':source_path,'sha256':checksum}],
            'generator':{'source':source_path,'sha256':checksum}}
    (HERE/('diagnostic-'+suffix+'-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')
    print(json.dumps({'source':source_path,'sha256':checksum,
                      'frames':len(trace),'graphs':len(graphs),'cameras':len(videos)}))


if __name__=='__main__':
    for suffix in ('reference','contrast'):
        build(suffix)
