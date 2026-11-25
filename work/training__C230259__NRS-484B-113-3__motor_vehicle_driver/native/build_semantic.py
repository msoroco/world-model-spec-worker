"""Build draft stage proposals from the exact frozen assignment and case bundles."""
import hashlib
import json
from pathlib import Path

from batch_pipeline.store import digest
from worker_exchange.semantic_delivery import validate

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
A=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
LAW=A['law_id'];CELL=A['cell_id'];ACTOR=A['actor'];TEMPLATE=LAW+'@'+ACTOR
PHRASE='yield the right-of-way'
NOTE='Physical precedence and responses are observations; legal right-of-way remains unresolved.'


def write(name,value):
    path=ROOT/'proposals'/(name+'.json');path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':'proposals/'+name+'.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    description=json.loads((ROOT/'native/bundles/controlled_1/construction.json').read_text())['recording_description']
    quote=A['law']['text']
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft','relevant_laws':[
        {'law_id':LAW,'quote':quote,'applies_to':[ACTOR],'relevance_type':'general_duty',
         'confidence':'low','notes':'Backing interaction is conditional in the frozen road/other-vehicle cell.'}],
        'borderline_excluded':[]}
    params=[{'name':'road_user_branch','kind':'world_setup','range_or_domain':'moving highway vehicle or pedestrian'},
        {'name':'backing_onset_s','kind':'controller','range_or_domain':'two authored onset windows; actual motion measured separately'}]
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':quote,
        'structure':{'activation':{'condition':'driver backs vehicle in section backing context','numeric_conditions':[]},
        'obligation':{'type':'must_yield','description':'yield to moving traffic and pedestrians',
            'source_clause':'Shall in every case yield the right-of-way to moving traffic and pedestrians.',
            'numeric_conditions':[]},'exceptions':[],
        'timing':{'description':'during backing with each present road user','numeric_conditions':[]},
        'judgment_calls_needed':[{'phrase':PHRASE,'note':NOTE}]},'parameter_refs':params}
    def o(name,unit,description):return {'name':name,'unit':unit,'description':description}
    requirement={'observables':[o('drv.backing','structured','Original signed reverse motion and body history'),
        o('drv.arrival_order','structured','Conflict-region entry sequence'),
        o('kin.velocity','structured','Road user motion and responses')],
        'context_inputs':[o('road_and_actor_context','structured','Original highway and actor identity readback')],
        'sweep_dimensions':[o('backing_onset_s','s','Observed first reverse movement time')],
        'landmarks':[],
        'recording_needs':[o('backing_onset_s','s','Sampled reverse onset time'),
            o('drv.yields_to','structured','Precedence facts without a legal outcome'),
            o('ru.pedestrian','structured','Pedestrian presence and motion where selected')],
        'limitations':['Timing, arrival order and braking do not establish legal right-of-way.',
                       'Physical motion and visibility require original CARLA review.']}
    judgment={'template_id':TEMPLATE,'phrase':PHRASE,'note':NOTE,'status':'draft',
        'observable_requirements':requirement}
    bindings={'cell_id':CELL,'actor':ACTOR,'status':'draft','established_contexts':[
        {'name':'road_other_vehicle_cell','source':'frozen catalog C230259'}],
        'law_refs':[{'template_id':TEMPLATE,'binding_kind':'general_duty'}],
        'context_refs':[],'fixed_parameters':[],
        'variable_parameters':[{**param,'used_by_laws':[LAW]} for param in params]}
    def assign(branch,onset):
        return {'road_user_branch':{'kind':'world_setup','value':branch,'unit':'categorical'},
                'backing_onset_s':{'kind':'controller','value':onset,'unit':'s'}}
    cases=[{'case_id':ROOT.name+'__baseline','target_law_id':None,'target_type':'baseline',
        'rationale':'Neutral road context; no original or accepted recording claimed.',
        'variable_assignments':assign('none',None),'unresolved_judgment_calls':[],
        'recording_description':description}]
    specs=[]
    for branch,stem in [('moving_traffic','controlled'),('pedestrian','pedestrian')]:
        sweep_id='c230259-'+branch+'-backing-onset'
        measurement={'method':'first original negative signed ego velocity',
            'time_window':'30 s original recording','statistic':'first'}
        axis={'variable':'backing_onset_s','observable':'backing_onset_s','unit':'s',
            'min':2.75,'max':12.25,'spacing':9.5,
            'range_rationale':'Two physical timing windows; no legal threshold is claimed.',
            'spacing_rationale':'Authored 55 and 245 frame starts at 20 Hz.',
            'feasibility_evidence':'Native runner command windows and saved source-shaped fixture.',
            'measurement':measurement}
        spec={'sweep_id':sweep_id,'target_law_id':LAW,'judgment_refs':[{'phrase':PHRASE,'note':NOTE}],
            'rationale':'Sample backing timing relative to '+branch+' motion while legal precedence remains unresolved.',
            'status':'complete','mode':'one_dimensional','axes':[axis],'landmarks':[],
            'variable_assignments':assign(branch,2.75),'recording_description':description}
        spec['spec_version']=digest(spec);spec['planned_case_count']=2
        spec['selection_order']=[ROOT.name+'__'+stem+'_2',ROOT.name+'__'+stem+'_1']
        specs.append(spec)
        for rank,(suffix,onset) in enumerate(((stem+'_2',2.75),(stem+'_1',12.25))):
            cases.append({'case_id':ROOT.name+'__'+suffix,'target_law_id':LAW,'target_type':'judgment_sweep',
                'rationale':spec['rationale'],'paired_probe_id':sweep_id,
                'deliberate_differences':['backing_onset_s'],
                'probe':{'primary_variable':'backing_onset_s',
                    'comparison_or_standard':'physical coverage; legal judgment unresolved',
                    'target_value_or_branch':{'backing_onset_s':onset}},
                'sweep_id':sweep_id,'sweep_spec_version':spec['spec_version'],
                'sweep_point':{'backing_onset_s':onset},'selection_rank':rank,
                'variable_assignments':assign(branch,onset),'recording_description':description,
                'judgment_refs':spec['judgment_refs'],
                'sweep_measurements':[{'variable':'backing_onset_s','observable':'backing_onset_s',
                    'unit':'s','measurement':measurement}],
                'unresolved_judgment_calls':[PHRASE]})
    proposal_cases={'cell_id':CELL,'actor':ACTOR,'status':'draft','sweep_specs':specs,
        'sweeps_expanded':True,'cases':cases}
    values={'relevance_batch':relevance,'relevance':relevance,'template':template,
        'judgment_observables':judgment,'bindings':bindings,'cases':proposal_cases}
    refs={name:write(name,value) for name,value in values.items()}
    refs['judgment_observables']=[refs['judgment_observables']]
    index={'format':'worker-semantic-delivery','assignment_id':ROOT.name,
        'stages':refs,'status':'draft','original_native_observed':False}
    write('semantic-index',index)
    manifest={'cases':[{'case_id':c['case_id'],
        'construction':'native/bundles/'+c['case_id'].rsplit('__',1)[1]+'/construction.json'}
        for c in cases if c['target_type']!='baseline']}
    print(validate(ROOT,A,manifest))


if __name__=='__main__':build()
