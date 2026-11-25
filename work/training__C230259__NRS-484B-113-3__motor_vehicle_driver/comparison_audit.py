"""Independent fixed-condition and backing-onset comparison from saved sources."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing source: '+path.name)
    return json.loads(path.read_text())

def audit(comparison_id,processing_specs,omit_case):
    plan=read(HERE/'case-plan.json')
    comparison=next((x for x in plan['comparisons'] if x['comparison_id']==comparison_id),None)
    if comparison is None:raise ValueError('Unknown comparison')
    paths=dict(item.split('=',1) for item in processing_specs)
    if set(paths)!=set(comparison['case_ids']) or omit_case:
        raise ValueError('Missing comparison case: '+str(omit_case or sorted(set(comparison['case_ids'])-set(paths))))
    manifest=read(HERE/'execution-manifest.json')
    observations=[]
    for case_id in comparison['case_ids']:
        selected=next(x for x in manifest['cases'] if x['case_id']==case_id)
        saved=read(paths[case_id])
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id')!=case_id or saved.get('candidate_id')!='primary' or
            saved.get('native_revision',{}).get('construction_sha256')!=sha(Path(saved['analysis_directory'])/'construction.json') or
            read(Path(saved['analysis_directory'])/'construction.json')!=read(HERE/selected['construction']) or
            saved.get('timestamp_joins',{}).get('frames')!=600):
            raise ValueError('Selected comparison source differs')
        stage=Path(saved['analysis_directory'])
        config=read(stage/'config.json');context=read(stage/'traffic-context.json')
        report=read(stage/'analysis-report.json');result=read(stage/'result.json')
        branch=case_id.rsplit('__',1)[1].startswith('pedestrian_')
        key='pedestrian_requirement' if branch else 'moving_requirement'
        measured=report.get('measurements',{}).get(key,{})
        if (measured.get('method')!=('measure_pedestrian_requirement' if branch else 'measure_moving_requirement') or
            any(measured.get('sources',{}).get(name)!=sha(stage/name)
                for name in ('native-motion.jsonl','traffic-context.json','video_frames.jsonl'))):
            raise ValueError('Comparison lacks original branch measurement')
        onset=result.get('realized_observables',{}).get('backing_onset_s',{})
        if (onset.get('method')!='first original negative signed ego velocity' or
            onset.get('reference')!='channels/backing_onset_s.jsonl' or
            not isinstance(onset.get('value'),(int,float))):
            raise ValueError('Original backing-onset observation missing')
        observations.append((case_id,config,context,measured['value'],onset['value'],sha(stage/'analysis-report.json')))
    configs=[row[1] for row in observations];contexts=[row[2] for row in observations]
    for field in ('law_id','cell_id','actor','rate_hz','duration_s','cameras','required_atoms','source_packets'):
        if any(config[field]!=configs[0][field] for config in configs[1:]):
            raise ValueError('Comparison fixed condition changed: '+field)
    for field in ('conflict_region','other_commanded_speed_mps','other_route_direction',
                  'pedestrian_actor_count_at_start'):
        if any(context[field]!=contexts[0][field] for context in contexts[1:]):
            raise ValueError('Comparison context changed: '+field)
    onsets=[row[4] for row in observations]
    if len(set(onsets))!=2 or not onsets[0]>onsets[1]:
        raise ValueError('Measured backing-onset difference missing')
    if any(row[3].get('backing_frames',0)<=0 or row[3].get('simultaneous_frames',0)<=0 for row in observations):
        raise ValueError('Comparison lacks simultaneous original observations')
    return {'format':'c230259-independent-comparison-audit-v1','comparison_id':comparison_id,
        'case_ids':comparison['case_ids'],'fixed_conditions_checked':True,
        'differences_checked':True,'measured_onset_s':dict(zip(comparison['case_ids'],onsets)),
        'analysis_sha256':{row[0]:row[5] for row in observations},
        'physical_or_legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',required=True)
    p.add_argument('--processing',action='append',required=True)
    p.add_argument('--omit-case');p.add_argument('--output',required=True)
    a=p.parse_args();result=audit(a.comparison,a.processing,a.omit_case)
    output=Path(a.output)
    if output.exists():raise ValueError('Retain previous comparison audit result')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'comparison_id':a.comparison}))

if __name__=='__main__':main()
