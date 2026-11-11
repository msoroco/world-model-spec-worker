"""Synthetic source-shaped C5191 physical outcome protocol, not a Native proof."""
import argparse,hashlib,json,os,sys
from pathlib import Path
from tempfile import TemporaryDirectory
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(ROOT/'.runtime-work/c5191-pipeline-output'))
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from turn_finalizer import analyze

def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def put(path,values):Path(path).write_text(''.join(json.dumps(v,allow_nan=False)+'\n' for v in values))
def run(case_id,kind):
    manifest=HERE/'execution-manifest.json';entry=next((x for x in json.loads(manifest.read_text())['cases'] if x['case_id']==case_id),None)
    if entry is None or kind not in ('complete_motion','incomplete_motion','missing_evidence'):raise ValueError('Unknown exact turn case or fixture kind')
    with TemporaryDirectory(prefix='turn-motion-',dir=ROOT/'.runtime-work') as temp:
        base=Path(temp);make_fixture(ROOT,ROOT/entry['fixture_recipe'],base/'fixture');make_attempt(manifest,case_id,base/'attempt');copy_sources(base/'fixture',base/'attempt');attempt=base/'attempt'
        source=attempt/'turn_originals.jsonl';samples=rows(source)
        if kind=='incomplete_motion':
            for row in samples:row['heading_xy']=[1.,0.]
            put(source,samples)
        if kind=='missing_evidence':source.unlink()
        sources={n:hashlib.sha256((attempt/n).read_bytes()).hexdigest() for n in ('video_frames.jsonl','trace.jsonl','turn_originals.jsonl','turn_scene_context.json') if (attempt/n).is_file()}
        value=None
        if kind=='missing_evidence':
            try:analyze(attempt,write_channel=False)
            except ValueError as exc:
                if 'Missing required source: turn_originals.jsonl' not in str(exc):raise
            else:raise ValueError('Missing turn source was accepted')
            status='unverified'
        else:
            value=analyze(attempt,write_channel=False)['measurements']['marked_turn_observation']['value'];suffix=case_id.rsplit('__',1)[-1]
            crossing=value['minimum_approach_clearance_m']<0;indicator=value['left_indicator_readback_frames']>0
            behavior=(not crossing if suffix=='left_turn_lane_contained_approach' else crossing and (indicator==suffix.endswith('_signaled')))
            status='met' if behavior and value['observed_heading_change_deg']>=45 else 'not_met'
        expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        if status!=expected:raise ValueError(f'Turn physical fixture {kind} yielded {status}, expected {expected}')
        return {'case_id':case_id,'fixture_kind':kind,'fixture_only':True,'diagnostic_fixture':True,'actual_native_capture':False,
                'physical_checks':{'maneuver':{'status':status,'method':'source-joined marked approach footprint, indicator and original heading protocol','sources':sources,'missing_evidence':['turn_originals.jsonl'] if kind=='missing_evidence' else []}},
                'maneuver_completed':status=='met','realized_observables':{'original_frame_count':value['frames'],'minimum_clearance_m':value['minimum_approach_clearance_m'],'observed_heading_change_deg':value['observed_heading_change_deg']} if value else {},
                'provenance_kind':'native','provenance_note':'Synthetic Native-shaped protocol only; no actual CARLA capture','physical_acceptance_claimed':False}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--kind',required=True,choices=('complete_motion','incomplete_motion','missing_evidence'));parser.add_argument('--output',required=True);args=parser.parse_args();Path(args.output).write_text(json.dumps(run(args.case,args.kind),indent=2)+'\n')
