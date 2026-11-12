"""Audit the canonical 21-case draft and both frozen physical sweep grids."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'runtime/pipeline'))
from scenario_pipeline.batch_pipeline.validation import coverage,recording_description
from scenario_pipeline.batch_pipeline.sweeps import validate_spec

def read(name):return json.loads((HERE/name).read_text())
def sha(name):return hashlib.sha256((HERE/name).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def audit(stage):
    plan=read('case-plan.json');binding=read('proposals/bindings.json')
    template=read('proposals/template.json')
    for judgment in template['structure']['judgment_calls_needed']:
        name='judgment-right-of-way.json' if judgment['phrase']=='yield the right-of-way' else 'judgment-extreme-right.json'
        evidence=read('proposals/'+name)
        judgment['observable_requirements']=evidence['observable_requirements']
    require(stage.get('status')=='draft' and stage.get('sweeps_expanded') is True and
            stage.get('original_native_accepted') is False and
            stage.get('candidate_only') is False,
            'Canonical 21-case delivery draft identity differs')
    ordinary=[c for c in stage['cases'] if c['target_type']!='judgment_sweep']
    timing=[c for c in stage['cases'] if c.get('sweep_id')=='C110919-right-of-way']
    lateral=[c for c in stage['cases'] if c.get('sweep_id')=='C110919-extreme-right']
    require(len(ordinary)==11 and len(timing)==len(lateral)==5 and
            [c['case_id'] for c in stage['cases'] if c['target_type']!='baseline']==
            [c['case_id'] for c in plan['cases']],
            'Ordinary or physical sweep case set differs')
    kinds={v['name']:v['kind'] for v in binding['variable_parameters']}
    require({'traffic_launch_frame','ego_entry_relative_to_signal_directed_traffic',
             'lateral_right_offset_m','full_body_lateral_position_in_highway',
             'approach_lane_and_highway_width'}<=set(kinds),
            'Canonical controller, measured or geometry binding missing')
    for case in stage['cases']:
        require(set(case['variable_assignments'])==set(kinds),
                'Case lacks full canonical variable assignments')
        require(all(v['kind']==kinds[name] and
                    (v['value'] is None if v['kind']=='subject_behavior' else True)
                    for name,v in case['variable_assignments'].items()),
                'Observed behavior authored or binding kind changed')
        recording_description(case['recording_description'])
    ids={c['case_id'] for c in stage['cases'] if c['target_law_id'] is not None}
    for requirement in plan['requirement_dispositions']:
        if requirement['status']=='selected_required':
            require(requirement['case_ids'] and set(requirement['case_ids'])<=ids,
                    'Selected requirement has unqualified or missing exact case IDs')
    specs={s['sweep_id']:s for s in stage['sweep_specs']}
    require(set(specs)=={'C110919-right-of-way','C110919-extreme-right'},
            'Exact physical sweep specs missing')
    for name,cases in (('C110919-right-of-way',timing),('C110919-extreme-right',lateral)):
        spec=specs[name];validate_spec(spec)
        require(spec['status']=='complete' and spec['planned_case_count']==5 and
                [c['case_id'] for c in cases]==spec['selection_order'] and
                all(c['sweep_spec_version']==spec['spec_version'] and
                    c['recording_description']==spec['recording_description'] for c in cases),
                'Frozen physical sweep version or case recording differs')
        axis=spec['axes'][0]
        for case in cases:
            require(case['variable_assignments'][axis['variable']]['value']==
                    case['sweep_point'][axis['variable']] and
                    case['variable_assignments'][axis['observable']]['value'] is None,
                    'Authored controller and measured outcome conflated')
    coverage(stage['cases'],binding,[template],stage['sweep_specs'])
    return {'format':'c110919-two-sweep-canonical-stage-audit-v1',
            'stage_sha256':sha('proposals/cases.json'),
            'binding_sha256':sha('proposals/bindings.json'),
            'case_plan_sha256':sha('case-plan.json'),
            'ordinary_cases':10,'timing_cases':5,'lateral_cases':5,
            'complete_sweep_specs':2,'canonical_delivery_selected':False}

def main():
    stage=read('proposals/cases.json');outcome=audit(stage)
    negative={}
    for name,mutate in (
        ('missing_lateral_case',lambda x:x['cases'].pop()),
        ('fabricated_lateral_measurement',lambda x:x['cases'][-1]['variable_assignments']['full_body_lateral_position_in_highway'].__setitem__('value',.05)),
        ('altered_lateral_point',lambda x:x['cases'][-1]['sweep_point'].__setitem__('lateral_right_offset_m',9)),
        ('missing_native_lane_channel',lambda x:x['sweep_specs'][0]['recording_description']['channels'].pop())):
        changed=copy.deepcopy(stage);mutate(changed)
        try:audit(changed)
        except ValueError as error:negative[name]=str(error)
        else:raise AssertionError('Damaged stage accepted: '+name)
    outcome['negative_rejections']=negative
    target=HERE/'update052-lateral-stage-audit.json'
    target.write_text(json.dumps(outcome,indent=2)+'\n')
    print(json.dumps({'ordinary_cases':10,'timing_cases':5,'lateral_cases':5,
        'negative_rejections':len(negative),'audit_sha256':sha(target)}))

if __name__=='__main__':main()
