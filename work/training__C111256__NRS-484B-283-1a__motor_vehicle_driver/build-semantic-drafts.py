"""Author source-bound early semantic stages; selected cases stage remains pending."""
from __future__ import annotations
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
source=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
law=source['law'];quote=law['text'];cell=source['cell'];actor=source['actor'];law_id=source['law_id']
P=HERE/'proposals';P.mkdir(exist_ok=True)
def save(name,value):(P/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
relevance={'cell_id':cell['cell_id'],'actor':actor,'status':'draft',
    'relevant_laws':[{'law_id':law_id,'quote':quote,'applies_to':[actor],
        'relevance_type':'specific_match','confidence':'medium',
        'notes':'Frozen intersection/travel/crosswalk cell can stage the uncontrolled ego-half witness; cited exceptions and opposite-half danger need independent review.'}],
    'borderline_excluded':[]}
for name in ('relevance_batch','relevance'):save(name,relevance)
phrase='in danger';note='Qualitative opposite-half proximity; no numeric cutoff is supplied by the law.'
template={'template_id':law_id+'@'+actor,'law_id':law_id,'actor':actor,'status':'draft',
    'quote':quote,'structure':{
        'activation':{'source_clause':'When official traffic-control devices are not in place or not in operation',
            'crossing':'pedestrian crossing the highway within a crosswalk',
            'half':'pedestrian upon ego travel/turn half or approaching closely from opposite half as to be in danger'},
        'obligation':{'type':'must_yield','actor':'driver of a vehicle',
            'action':'yield the right-of-way, slowing down or stopping if need be so to yield',
            'source_clause':'the driver of a vehicle shall yield the right-of-way, slowing down or stopping if need be so to yield'},
        'exceptions':[
            {'source_clause':'Except as otherwise provided in NRS 484B.287',
             'status':'applicability_requires_separate_source_review'},
            {'source_clause':'484B.290','status':'physical_eligibility_unverified'},
            {'source_clause':'484B.350','status':'applicability_requires_separate_source_review'}],
        'timing':{'kind':'while_protected_crossing_conflict_exists','source_clause':'when the pedestrian is upon the half of the highway'},
        'judgment_calls_needed':[{'phrase':phrase,'note':note}]},
    'parameter_refs':[]}
save('template',template)
requirements={'observables':[
        {'name':'drv.yields_to','unit':'structured','description':'Original frame-joined pedestrian occupancy and ego crossing conflict history.'},
        {'name':'native_body_pose_control','unit':'structured','description':'Original vehicle body pose and control history across the crosswalk.'}],
    'context_inputs':[],'sweep_dimensions':[], 'landmarks':[],
    'recording_needs':[{'name':'drv.yields_to','unit':'structured','description':'Pedestrian and ego conflict timing on the governed highway half.'}],
    'limitations':['Qualitative danger and legal right of way require independent review; no numeric threshold is inferred from these measurements.']}
judgment={'template_id':template['template_id'],'phrase':phrase,'note':note,'status':'draft',
          'observable_requirements':requirements}
save('judgment_observables_danger',judgment)
common={'request':{'cell':cell,'actor':actor},'law_records':{law_id:law},'dependencies':[]}
for name in ('relevance_batch','relevance'):stages.validate(name,json.loads((P/(name+'.json')).read_text()),common)
rules=json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
stages.validate('template',json.loads((P/'template.json').read_text()),
    {'request':{'law_id':law_id,'actor':actor},'law_record':law,'canonical_parameter_rules':rules,'dependencies':[]})
stages.validate('judgment_observables',json.loads((P/'judgment_observables_danger.json').read_text()),
    {'request':{'template_id':template['template_id'],'phrase':phrase,'note':note},'dependencies':[]})
print('validated 4 early semantic stage proposals')
