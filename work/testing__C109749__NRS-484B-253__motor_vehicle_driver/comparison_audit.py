"""Independent C109749 reciprocal-response comparison of retained original sources.

Diagnostic output tests software checks and never asserts physical or legal acceptance.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from delivery_audit import validate_originals
from measurements import analyze

COMPARISON='reciprocal_response_after_turn'
IDENTITY={'selected_case_id','supported_case_ids'}
COMMON_FILES={'camera_setup.py','camera_encoder.py','capture_sources.py','construction.py',
              'controller.py','native_scene.py','measurements.py'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def embedded(folder,entry):
    path=folder/entry['construction']
    if sha(path)!=entry['construction_sha256']:
        raise ValueError('Comparison construction hash changed')
    return {f['path']:f['content'] for f in read(path)['files']}


def normalize_runner(text,case_id):
    text=text.replace(case_id,'<CASE>')
    positive="later_target = (0.0 if command['state'] in ('turn','complete')\n                                        else config['reciprocal_approach_speed_mps'])"
    negative="later_target = config['reciprocal_approach_speed_mps']  # controlled continued approach"
    if positive in text:text=text.replace(positive,'later_target = <CONTROLLED_RECIPROCAL_POLICY>')
    elif negative in text:text=text.replace(negative,'later_target = <CONTROLLED_RECIPROCAL_POLICY>')
    else:raise ValueError('Declared reciprocal policy not found in runner')
    return text


def center(actor):
    vertices=actor['body_vertices_xy_m']
    return tuple((min(v[i] for v in vertices)+max(v[i] for v in vertices))/2 for i in (0,1))


def audit_pair(folder,comparison_id,left_source,right_source,*,left_audit=None,right_audit=None,
               diagnostic_selftest=False):
    folder=Path(folder);left_source=Path(left_source);right_source=Path(right_source)
    plan=read(folder/'case-plan.json');manifest=read(folder/'execution-manifest.json')
    pair=next((x for x in plan['comparisons'] if x['comparison_id']==comparison_id),None)
    if pair is None or comparison_id!=COMPARISON or len(pair.get('case_ids',[]))!=2:
        raise ValueError('Exact reciprocal comparison plan required')
    entries=[next((e for e in manifest['cases'] if e['case_id']==cid),None) for cid in pair['case_ids']]
    if any(e is None for e in entries):raise ValueError('Comparison manifest case missing')
    left_files,right_files=[embedded(folder,e) for e in entries]
    for name in COMMON_FILES:
        if left_files.get(name)!=right_files.get(name):
            raise ValueError('Fixed construction source differs: '+name)
    if normalize_runner(left_files['runner.py'],entries[0]['case_id'])!=normalize_runner(right_files['runner.py'],entries[1]['case_id']):
        raise ValueError('Runner differs outside declared reciprocal policy')
    configs=[json.loads(files['config.json']) for files in (left_files,right_files)]
    fixed=[{k:v for k,v in cfg.items() if k not in IDENTITY} for cfg in configs]
    if fixed[0]!=fixed[1]:
        raise ValueError('Fixed authored configuration differs')
    if configs[0]['rate_hz']!=20 or configs[0]['duration_s']!=45 or len(configs[0]['cameras'])!=4:
        raise ValueError('Comparison capture contract changed')
    joins=[validate_originals(root,e['case_id'],full_duration=not diagnostic_selftest)
           for root,e in zip((left_source,right_source),entries)]
    geometry=[read(root/'intersection_geometry.json') for root in (left_source,right_source)]
    if geometry[0]!=geometry[1]:
        raise ValueError('Fixed original junction geometry differs')
    histories=[rows(root/'interaction_history.jsonl') for root in (left_source,right_source)]
    if len(histories[0])!=len(histories[1]):
        raise ValueError('Comparison original duration differs')
    measured=[analyze(root) for root in (left_source,right_source)]
    if measured[0]['reciprocal_stopped_outside_during_turn'] is not True or measured[1]['reciprocal_stopped_outside_during_turn'] is not False:
        raise ValueError('Declared reciprocal response difference absent')
    starts=[m['ego_turn_start_frame'] for m in measured]
    if any(v is None for v in starts):raise ValueError('Original subject turn onset missing')
    indexes=[next(i for i,r in enumerate(history) if r['frame']==start) for history,start in zip(histories,starts)]
    if abs(indexes[0]-indexes[1])>2:
        raise ValueError('Fixed subject turn timing differs')
    for i in range(min(indexes)+1):
        a,b=histories[0][i],histories[1][i]
        if abs((a['time_s']-histories[0][0]['time_s'])-(b['time_s']-histories[1][0]['time_s']))>0.05:
            raise ValueError('Fixed original timing differs')
        for role in ('ego','oncoming'):
            if math.dist(center(a[role]),center(b[role]))>2.0 or math.dist(a[role]['velocity_xy_mps'],b[role]['velocity_xy_mps'])>1.0:
                raise ValueError('Fixed initial actor trajectory differs: '+role)
    if not diagnostic_selftest:
        for path,e,joined in zip((left_audit,right_audit),entries,joins):
            if path is None or not Path(path).is_file():raise ValueError('Independent delivery audit missing')
            receipt=read(path)
            if (receipt.get('format')!='worker-delivery-audit' or receipt.get('passed') is not True or
                    receipt.get('case_id')!=e['case_id'] or receipt.get('original_sources',{}).get('history_sha256')!=joined['history_sha256']):
                raise ValueError('Independent delivery audit missing or stale')
    return {'format':'worker-comparison-audit-diagnostic' if diagnostic_selftest else 'worker-comparison-audit',
            'passed':not diagnostic_selftest,'software_checks_passed':True,'diagnostic_fixture':diagnostic_selftest,
            'physical_acceptance_claimed':False,'legal_verdict_asserted':False,
            'comparison_id':comparison_id,'case_ids':pair['case_ids'],'fixed_conditions':pair['fixed_conditions'],
            'deliberate_differences':pair['deliberate_differences'],
            'frames':len(histories[0]),'left_source_sha256':joins[0]['history_sha256'],
            'right_source_sha256':joins[1]['history_sha256'],
            'geometry_sha256':joins[0]['geometry_sha256'],
            'observed_reciprocal_stopped_outside':[True,False],
            'turn_start_indexes':indexes}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--folder',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--comparison',required=True)
    p.add_argument('--left-source',type=Path,required=True)
    p.add_argument('--right-source',type=Path,required=True)
    p.add_argument('--left-audit',type=Path)
    p.add_argument('--right-audit',type=Path)
    p.add_argument('--diagnostic-selftest',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit_pair(a.folder,a.comparison,a.left_source,a.right_source,
                    left_audit=a.left_audit,right_audit=a.right_audit,
                    diagnostic_selftest=a.diagnostic_selftest)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
