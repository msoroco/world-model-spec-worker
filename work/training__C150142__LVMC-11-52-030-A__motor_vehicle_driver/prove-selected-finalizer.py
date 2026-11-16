"""Run source-derived saved finalization on explicit synthetic Native samples."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.measurement_contract import validate as validate_contract

CASE=ROOT.name+'__reference'
MANIFEST=ROOT/'selected-primary/reference/draft-manifest.json'
VIEWS=('overview','approach','reference_corner','driver_reference')


def write_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in items))


def sources(attempt):
    actors=[];frames=[];trace=[];evidence=[]
    for i in range(240):
        x=40*min(i,120)/120
        y=-6.8
        actors.append({'frame':i,'native_frame':i,'time_s':i/20,
                       'source_kind':'synthetic_native_sample',
                       'ego_center_native_xy_m':[x,y],
                       'ego_body_native_xy_m':[[x-1,y-.5],[x+1,y-.5],
                                                [x+1,y+.5],[x-1,y+.5]],
                       'velocity_native_xyz_mps':[1 if i<120 else 0,0,0],
                       'yaw_deg':0})
        frames.append({'video_frame':i,'native_frame':i,'carla_frame':i,
                       'time_s':i/20,'views':list(VIEWS)})
        trace.append({'frame':i,'time_s':i/20,'position_m':[x,y,0],
                      'speed_mps':1 if i<120 else 0})
        evidence.append({'frame':i,'source_kind':'synthetic_native_sample'})
    write_rows(attempt/'native-raw-actors.jsonl',actors)
    write_rows(attempt/'video_frames.jsonl',frames)
    write_rows(attempt/'trace.jsonl',trace)
    write_rows(attempt/'capture/evidence.jsonl',evidence)
    (attempt/'native-map-readback.json').write_text(json.dumps({
        'source_kind':'synthetic_native_sample','paint_color':'red',
        'red_curb_start_x_m':30,'red_curb_end_x_m':50,'curb_y_m':-7})+'\n')
    for view in VIEWS:
        (attempt/(view+'.mkv')).write_bytes(b'synthetic placeholder; not decoded')


def run(attempt):
    p=subprocess.run([sys.executable,str(attempt/'finalize_selected.py'),
        '--attempt',str(attempt),'--output',str(attempt/'analysis-report.json')],
        cwd=attempt,env=execution_env(),capture_output=True,text=True)
    return p


def prove():
    contract=json.loads((ROOT/'selected-primary/reference/selected-measurement-contracts/reference.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    if len(validate_contract(contract,plan['requirement_dispositions'],
                            (ROOT/'native/finalize_selected.py').read_text(),CASE))!=5:
        raise AssertionError('Selected requirement measurement contract differs')
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='C150142-saved-') as tmp:
        parent=Path(tmp)
        positive=parent/'positive'
        materialize(MANIFEST,CASE,positive)
        sources(positive)
        p=run(positive)
        if p.returncode:
            raise AssertionError('Synthetic saved finalizer failed: '+p.stderr[-1000:])
        report=json.loads((positive/'analysis-report.json').read_text())
        result=json.loads((positive/'result.json').read_text())
        if report['measurements']['red_curb_stop_or_park_observed']['value'] is not True or \
           result['provenance_kind']!='synthetic_local_diagnostic' or \
           result['measured_values']['red_curb_stopped_frames']!=119 or \
           not all((positive/'channels'/(name+'.jsonl')).is_file() for name in
                   ('ego_pose','ego_speed','red_curb_stop_or_park','four_source_views')):
            raise AssertionError('Synthetic saved observations differ')
        negative=parent/'negative'
        materialize(MANIFEST,CASE,negative)
        sources(negative)
        (negative/'native-map-readback.json').unlink()
        rejected=run(negative)
        if rejected.returncode==0 or \
           'Missing required source: native-map-readback.json' not in rejected.stderr:
            raise AssertionError('Missing red-curb map source was accepted')
        provenance=parent/'provenance-negative'
        materialize(MANIFEST,CASE,provenance)
        sources(provenance)
        actor_path=provenance/'native-raw-actors.jsonl'
        altered=[json.loads(line) for line in actor_path.read_text().splitlines()]
        for row in altered:
            row['source_kind']='original_native'
        write_rows(actor_path,altered)
        rejected_provenance=run(provenance)
        if rejected_provenance.returncode==0 or \
           'Original actor positions cannot use fixture curb paint' not in rejected_provenance.stderr:
            raise AssertionError('Fixture curb paint was accepted as Native')
    return {'format':'c150142-saved-finalizer-cpu-proof-v1','passed':True,
            'positive_red_curb_stopped_frames':119,
            'negative_rejected':['missing-native-map-readback',
                                 'fixture-paint-as-original-native'],
            'source_kind':'synthetic_native_sample','actual_media_decoded':False,
            'process_saved_passed':False,'original_native_observed':False,
            'physical_acceptance_claimed':False}


if __name__=='__main__':print(json.dumps(prove(),sort_keys=True))
