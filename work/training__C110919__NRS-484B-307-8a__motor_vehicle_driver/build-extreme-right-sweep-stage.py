"""Expand a physical lateral coverage grid without making a legal finding."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'runtime/pipeline'))
sys.path.insert(0,str(HERE/'native'))
from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps,validate_spec
from extreme_right_sweep import LateralOffset

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    stage=read(HERE/'proposals/cases.json')
    binding=read(HERE/'proposals/bindings.json')
    template=read(HERE/'proposals/template.json')
    if not stage.get('sweeps_expanded') or any(c.get('sweep_id')=='C110919-extreme-right' for c in stage['cases']):
        raise ValueError('Canonical stage is not the 16-case pre-lateral source')
    spec=next(s for s in stage['sweep_specs'] if s['sweep_id']=='C110919-extreme-right')
    if spec['status']!='incomplete':raise ValueError('Lateral sweep is already complete')
    source=next(c for c in stage['cases'] if c.get('sweep_id')=='C110919-right-of-way' and
                c['sweep_point']['traffic_launch_frame']==30)
    body=json.loads(read(HERE/'traffic_branch_cases/traffic_yield_wait-diagnostic.json')
                    ['files']['native_samples.jsonl'].splitlines()[0])['native_body_xy_m']
    half_width=(max(p[0] for p in body)-min(p[0] for p in body))/2
    if abs(half_width-1.1)>1e-6 or 1.75+.6+half_width>3.5:
        raise ValueError('Diagnostic body cannot fit the authored right lane at maximum offset')
    for value in (0,.15,.3,.45,.6):LateralOffset(value).route()
    observed='full_body_lateral_position_in_highway'
    control='lateral_right_offset_m'
    spec.update(status='complete',mode='one_dimensional',landmarks=[],
        rationale='Vary the authored ego route toward the surveyed right highway edge; measure the original full-body edge clearance without assigning a legal cutoff.',
        axes=[{'variable':control,'observable':observed,'unit':'m',
            'min':0,'max':.6,'spacing':.15,
            'measurement':{'method':'saved Native full-body rightmost extent relative to surveyed approach highway right edge',
                           'time_window':'all original south-approach frames before turn',
                           'statistic':'min'},
            'range_rationale':'The authored right lane is 3.5 m wide with center x=1.75 m. The 2.2 m diagnostic body leaves 0.65 m center-offset room to its right edge; 0.6 m leaves a 0.05 m diagnostic geometric margin. Native blueprint dimensions and realized motion still require capture.',
            'spacing_rationale':'0.15 m gives five distinct route and spawn setpoints across the feasible authored corridor; it is a sampling interval, not a legal tolerance.',
            'feasibility_evidence':'LateralOffset builds five continuous 819-point routes; diagnostic first-frame 2.2 m body fits 0..3.5 m lane at all five setpoints; original Native vehicle width and lane readback are checked before capture.'}],
        variable_assignments=deepcopy(source['variable_assignments']),
        recording_description=deepcopy(source['recording_description']))
    spec.pop('missing_inputs',None)
    spec['variable_assignments']['traffic_launch_frame']={'kind':'controller','value':30,
        'note':'Held fixed for lateral comparison; observed traffic motion measured separately'}
    spec['variable_assignments'][control]={'kind':'controller','value':0,
        'note':'Authored ego spawn and continuous route offset toward the right edge'}
    spec['variable_assignments'][observed]={'kind':'subject_behavior','value':None,
        'note':'Measured original full-body minimum right-edge clearance; no authored value'}
    spec['variable_assignments']['approach_lane_and_highway_width']={
        'kind':'world_setup','value':None,
        'note':'Read original Native approach and neighboring lane widths; no authored observed value'}
    spec['recording_description']['channels'].extend([
        {'name':'native_lane_geometry','unit':'structured','sampling_rate_hz':20,
         'method':'Per-frame original Native waypoint road, lane, width and right edge readback',
         'time_window':'entire 24 s / 480-frame attempt',
         'reference_frame':'Native map frame joined to body and four cameras',
         'uncertainty':'Map projection and body footprint require independent original review'},
        {'name':observed,'unit':'m','sampling_rate_hz':20,
         'method':'Postcapture right highway edge minus original Native rightmost body x for all approach frames',
         'time_window':'south approach before turn in 24 s attempt',
         'reference_frame':'surveyed Native road 1 right edge and original frame identity',
         'uncertainty':'Original lane boundary and body/camera joins require independent review'}])
    spec['recording_description']['context_inputs'].extend([
        {'name':control,'unit':'m','method':'Selected exact config and retained Native controller request'},
        {'name':'approach_lane_and_highway_width','unit':'m',
         'method':'Original Native approach and adjacent lane widths and boundary coordinates'}])
    spec['recording_description']['limitations'].append(
        'No numerical right-edge clearance in this sweep is a legal extreme-right threshold')
    for item in stage['cases']:
        item['variable_assignments'].setdefault(control,{'kind':'controller','value':None,
            'note':'Lateral sweep control does not apply to this case'})
        item['variable_assignments'].setdefault(observed,{'kind':'subject_behavior','value':None,
            'note':'Original full-body lateral clearance unmeasured'})
        item['variable_assignments'].setdefault('approach_lane_and_highway_width',{
            'kind':'world_setup','value':None,'note':'Original Native lane and highway widths unmeasured'})
    for name,kind,domain in ((control,'controller',[0,.15,.3,.45,.6]),
                             (observed,'subject_behavior',[-3.5,3.5]),
                             ('approach_lane_and_highway_width','world_setup',[0,7])):
        if name not in {x['name'] for x in binding['variable_parameters']}:
            binding['variable_parameters'].append({'name':name,'kind':kind,
                'range_or_domain':domain,'used_by_laws':['NRS-484B-307-8a']})
    validate_spec(spec)
    mini={'cases':[],'sweep_specs':[deepcopy(spec)]}
    expand_sweeps(mini,[template],binding)
    cases=mini['cases']
    if len(cases)!=5 or {c['sweep_point'][control] for c in cases}!={0,.15,.3,.45,.6}:
        raise ValueError('Expanded lateral grid differs')
    stage['cases'].extend(cases)
    stage['sweep_specs']=[mini['sweep_specs'][0] if s['sweep_id']==spec['sweep_id'] else s
                          for s in stage['sweep_specs']]
    stage['candidate_only']=True
    stage['original_native_accepted']=False
    out=HERE/'proposals/extreme-right-sweep-candidate.json'
    out.write_text(json.dumps(stage,indent=2)+'\n')
    (HERE/'proposals/extreme-right-bindings-candidate.json').write_text(
        json.dumps(binding,indent=2)+'\n')
    return out,cases

if __name__=='__main__':
    out,cases=build()
    print(json.dumps({'candidate_stage':str(out),'sha256':sha(out),
        'cases':[c['case_id'] for c in cases],'original_native_accepted':False}))
