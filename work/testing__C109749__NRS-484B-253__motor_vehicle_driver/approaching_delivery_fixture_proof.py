"""Build a full-duration synthetic C109749 audit fixture, never a delivery receipt."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
REPO=FOLDER.parents[1]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result
from worker_exchange.media import compose_four_views
from worker_exchange.capture import PROFILE
from approaching_delivery_audit import CAMERAS,APPROACHING_BRANCHES,audit_attempt,sha
from approaching_yield_observation import observe as observe_yield
from approaching_no_yield_observation import observe as observe_no_yield


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def lines(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(item,allow_nan=False,separators=(',',':'))+'\n' for item in items))


def build_positive(root,case):
    if root.exists():
        raise ValueError('Use a fresh diagnostic root')
    root.mkdir(parents=True)
    attempt=root/'attempt';attempt.mkdir()
    draft=FOLDER/'cases'/('approaching_yield' if APPROACHING_BRANCHES[case]=='yield' else 'approaching_no_yield')
    entry=json.loads((draft/'draft-manifest.json').read_text())['cases'][0]
    recipe=json.loads((draft/'diagnostic-recipe.json').read_text())
    diagnostic=json.loads((REPO/recipe['generator']['source']).read_text())['files']
    construction=json.loads((draft/entry['construction']).read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    write(attempt/'config.json',config)
    (attempt/'intersection_geometry.json').write_text(diagnostic['intersection_geometry.json'])
    original=[json.loads(s) for s in diagnostic['interaction_history.jsonl'].splitlines() if s]
    base_frame=original[0]['frame']
    count=config['rate_hz']*config['duration_s']
    history=[];mapping=[];trace=[]
    for index in range(count):
        row=copy.deepcopy(original[min(index,len(original)-1)])
        frame=base_frame+index;time=round((index+1)/config['rate_hz'],6)
        row['frame']=frame;row['time_s']=time
        history.append(row)
        mapping.append({'video_frame':index,'carla_frame':frame,'native_frame':frame,'time_s':time})
        trace.append({'frame':frame,'time_s':time})
    lines(attempt/'interaction_history.jsonl',history)
    lines(attempt/'video_frames.jsonl',mapping)
    lines(attempt/'trace.jsonl',trace)
    write(attempt/'converted/trace.json',{'scenes':[{'t':round(row['time_s']*1000)} for row in mapping]})
    write(attempt/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'scope':'CPU software audit fixture; no physical recording'})
    observed=(observe_yield if APPROACHING_BRANCHES[case]=='yield' else observe_no_yield)(attempt)
    key='approaching_yield_samples' if APPROACHING_BRANCHES[case]=='yield' else 'opposing_entry_frame'
    result=physical_result(attempt,{'case_id':case,'measured_values':{
        'initial_oncoming_clearance_frame':observed.get('initial_oncoming_clearance_frame',observed.get('opposing_clearance_frame')),
        'ego_turn_start_frame':observed['ego_turn_start_frame'],
        key:observed[key]},
        'target_checks':[],'realized_observables':{},'setup_confirmed':False,
        'behavior_attempted':False,'maneuver_completed':False})
    if (result['physical_checks']['setup']['status']!='met' or
            result['physical_checks']['maneuver']['status']!='met'):
        raise ValueError('Full-duration synthetic motion did not satisfy source-bound diagnostic checks')
    write(attempt/'result.json',result)
    sizes={'overview':PROFILE['overview'],**dict(zip(CAMERAS[1:],PROFILE['detail_views']))}
    for name,(width,height) in sizes.items():
        source=attempt/(name+'.mkv')
        vf='drawbox=x=20:y=20:w=64:h=64:color=red:t=fill'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                        '-i',f'color=c=black:s={width}x{height}:r=20','-vf',vf,
                        '-frames:v',str(count),'-c:v','ffv1','-pix_fmt','yuv444p',str(source)],check=True)
    compose_four_views({name:attempt/(name+'.mkv') for name in CAMERAS},
                       attempt/'video_frames.jsonl',attempt/'raw.mkv')
    names=('config.json','interaction_history.jsonl','intersection_geometry.json','video_frames.jsonl',
           'trace.jsonl',*(name+'.mkv' for name in CAMERAS))
    sealed={name:sha(attempt/name) for name in names}
    write(attempt/'capture-seal.json',{'format':'worker-sealed-capture','provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'frames':count,'sources':sealed,
          'events':['capture_finished','encoders_closed','restoration_verified'],
          'physical_acceptance_claimed':False})
    write(attempt/'native-exit.json',{'event':'native_exit',
          'capture_seal_sha256':sha(attempt/'capture-seal.json')})
    write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
          'native_exit_sha256':sha(attempt/'native-exit.json'),'diagnostic_fixture':True})
    review={'case_id':case,'reviewer':'synthetic CPU fixture generator',
            'method':'static red test pattern; no actor identity or real visibility assertion',
            'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'source_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS},
            'observations':[{'camera':name,'video_frame':0,'actor':role,
                             'actor_id':history[0][role]['actor_id'],'bbox_xyxy':[0,0,100,100]}
                            for name in CAMERAS for role in ('ego','oncoming','reciprocal')]}
    write(root/'pixel-review.json',review)
    return attempt


def positive(root,case):
    attempt=build_positive(root,case)
    receipt=audit_attempt(attempt,case,'diagnostic-job',1,'diagnostic-recording',
                          root/'pixel-review.json',attempt/'diagnostic-audit.json',
                          root/'source-decode.json',diagnostic_selftest=True)
    if (receipt['passed'] is not False or receipt['software_checks_passed'] is not True or
            receipt['diagnostic_fixture'] is not True or receipt['frames']!=900):
        raise ValueError('Diagnostic audit incorrectly claimed physical acceptance')
    print(json.dumps({'case_id':case,'software_checks_passed':True,'frames':receipt['frames'],
                      'diagnostic_fixture':True,'physical_acceptance_claimed':False,
                      'audit_sha256':sha(attempt/'diagnostic-audit.json')}))


def negative(root,source_root,case):
    if root.exists():
        raise ValueError('Use a fresh negative diagnostic root')
    source=Path(source_root).resolve()/'attempt'
    if not (source/'diagnostic-audit.json').is_file():
        raise ValueError('Positive diagnostic audit required first')
    attempt=root/'attempt';attempt.mkdir(parents=True)
    for name in ('config.json','result.json','capture-seal.json','native-exit.json','owner-release.json'):
        (attempt/name).write_bytes((source/name).read_bytes())
    # A sealed source is absent; the audit must fail before any decode or pixel review.
    audit_attempt(attempt,case,'diagnostic-job',1,'diagnostic-recording',
                  source_root/'pixel-review.json',attempt/'diagnostic-audit.json',
                  root/'source-decode.json',diagnostic_selftest=True)
    raise ValueError('Missing sealed original was accepted')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--negative-source-root',type=Path)
    a=p.parse_args()
    if a.case not in APPROACHING_BRANCHES:
        raise ValueError('Exact C109749 audit case required')
    if a.negative_source_root:
        negative(a.output_root.resolve(),a.negative_source_root.resolve(),a.case)
    else:
        positive(a.output_root.resolve(),a.case)


if __name__=='__main__':main()
