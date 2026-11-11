"""Synthetic Native-shaped backing outcome fixtures; never actual physical findings."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,tempfile,sys
from pathlib import Path
folder=Path(__file__).resolve().parent;repo=folder.parents[1]
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(case,kind):
    manifest=json.loads((folder/'execution-manifest.json').read_text())
    entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Unknown exact backing case')
    if kind not in ('complete_motion','incomplete_motion','missing_evidence'):raise ValueError('Unknown physical fixture kind')
    with tempfile.TemporaryDirectory(prefix='backing-physical-',dir=repo/'.runtime-work') as temporary:
        attempt=Path(temporary)/'fixture'
        materialize(repo,repo/entry['fixture_recipe'],attempt)
        if kind=='incomplete_motion':
            history=[json.loads(line) for line in (attempt/'backing_history.jsonl').read_text().splitlines()]
            trace=[json.loads(line) for line in (attempt/'trace.jsonl').read_text().splitlines()]
            first=history[0]['ego']['position_m'][0]
            for h,t in zip(history,trace):
                shift=first-h['ego']['position_m'][0]
                h['ego']['position_m'][0]=first
                for vertex in h['ego']['body_vertices_m']:vertex[0]+=shift
                t['position_m'][0]=first;t['position']['x']=first
            (attempt/'backing_history.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in history))
            (attempt/'trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in trace))
        elif kind=='missing_evidence':(attempt/'backing_history.jsonl').unlink()
        construction=json.loads((folder/entry['construction']).read_text())
        source=next(f for f in construction['files'] if f['path']=='backing_finalizer.py')['content']
        module_path=attempt/'backing_finalizer.py';module_path.write_text(source)
        spec=importlib.util.spec_from_file_location('physical_backing_finalizer',module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        sources={n:sha(attempt/n) for n in ('video_frames.jsonl','trace.jsonl','backing_history.jsonl') if (attempt/n).is_file()}
        status={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        observed=None
        try:observed,_=module.measure_reverse_encounter(attempt)
        except ValueError as error:
            expected={'incomplete_motion':'Original reverse displacement absent','missing_evidence':'Missing required source: backing_history.jsonl'}.get(kind)
            if expected is None or expected not in str(error):raise
        if (observed is not None)!=(kind=='complete_motion'):raise ValueError('Physical fixture outcome disagrees with source')
        return {'case_id':case,'fixture_kind':kind,'fixture_only':True,'diagnostic_fixture':True,'actual_native_capture':False,
                'physical_checks':{'maneuver':{'status':status,'method':'Original-shaped reverse gear and ego position samples joined to other vehicle state; synthetic fixture','sources':sources,'missing_evidence':['backing_history.jsonl'] if kind=='missing_evidence' else []}},
                'maneuver_completed':status=='met','realized_observables':{'reverse_displacement_m':observed['reverse_displacement_m'],'min_center_distance_m':observed['min_center_distance_m']} if observed else {},
                'provenance_kind':'native','provenance_note':'Native-shaped protocol fixture, never an actual Native acquisition','physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--kind',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 result=run(a.case,a.kind);Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(a.case,a.kind,result['physical_checks']['maneuver']['status'],'synthetic fixture only')
if __name__=='__main__':main()
