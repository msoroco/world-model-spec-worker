"""Source-quoted canonical stages and exact source-observation planning."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
FOLDER=HERE.parent
ROOT=FOLDER.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    original=json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
    law=original['law'];quote=law['text'];law_id=law['id'];actor=original['actor'];cell=original['cell_id']
    rel={'cell_id':cell,'actor':actor,'status':'draft',
        'relevant_laws':[{'law_id':law_id,'quote':quote,'applies_to':[actor],
            'relevance_type':'specific_match','confidence':'low',
            'notes':'Frozen one-way angle-bay cell; City Traffic Engineer street designation and actual marking require original source review.'}],
        'borderline_excluded':[]}
    write(FOLDER/'proposals/relevance.json',rel)
    write(FOLDER/'proposals/relevance_batch.json',rel)
    tid=law_id+'@'+actor
    template={'template_id':tid,'law_id':law_id,'actor':actor,'status':'draft','quote':quote,
        'structure':{'law_id':law_id,
            'activation':{'condition':'Angle parking is permitted at the street and the subject stands or parks a vehicle there; City decision and signage or markings need independent source review','numeric_conditions':[]},
            'obligation':{'type':'must','description':'Vehicle front points toward lawful traffic movement while standing or parked where angle parking is permitted','source_clause':'the front of the vehicle is pointed toward the direction of lawful traffic movement','numeric_conditions':[]},
            'exceptions':[],
            'timing':{'description':'During standing or parking; no numeric angle tolerance in the quoted law','numeric_conditions':[]},
            'judgment_calls_needed':[]},
        'parameter_refs':[{'name':'requested_front_yaw_deg','kind':'controller','range_or_domain':'angle parking orientation request'},
            {'name':'observed_front_direction','kind':'subject_behavior','range_or_domain':'source measured toward or against one-way lawful traffic direction'},
            {'name':'one_way_road','kind':'world_setup','range_or_domain':'one-way street candidate; original lawful direction source required'}]}
    write(FOLDER/'proposals/template.json',template)
    binding={'cell_id':cell,'actor':actor,'status':'draft',
        'established_contexts':[{'name':'one_way_angle_bay_candidate',
            'source':'frozen catalog cell; City permission, sign and actual marking not established by authored proposal'}],
        'law_refs':[{'template_id':tid,'binding_kind':'direct'}],
        'context_refs':[],'fixed_parameters':[],
        'variable_parameters':[dict(item,used_by_laws=[law_id]) for item in template['parameter_refs']]}
    write(FOLDER/'proposals/bindings.json',binding)
    stages={name:{'path':'proposals/'+filename,'sha256':sha(FOLDER/'proposals'/filename)}
        for name,filename in (('relevance_batch','relevance_batch.json'),('relevance','relevance.json'),
                              ('template','template.json'),('bindings','bindings.json'),('cases','cases.json'))}
    stages['judgment_observables']=[]
    write(FOLDER/'proposals/semantic-index.json',{'format':'worker-semantic-delivery',
        'assignment_id':FOLDER.name,'stages':stages})
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    plan['source_topic_inventory']=[{'topic_id':key,'source':topic['source'],
        'text':topic['text'],'disposition':'selected_required',
        'case_ids':[FOLDER.name+'__probe_a',FOLDER.name+'__probe_b']}
        for key,topic in json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][law_id]['topics'].items()]
    plan['source_observation_mapping']={item['term']:{
        'evidence':'600-frame source channel and separate Native or City source review',
        'channels':[item['term']],
        'source_refs':['native_samples.jsonl','road_geometry.json','permission_authority.json']}
        for item in original['source_observation_terms']}
    plan['camera_plan']={'profile':'overview1080-capability','duration_s':30,
        'composition':'synchronized_four_view_primary',
        'coverage':[{'subject':'parked vehicle front and bay','interval':'full 30 s',
            'view':name} for name in ('overview','approach','reference_corner','driver_reference')]}
    write(FOLDER/'case-plan.json',plan)
    print(json.dumps({'semantic_index_sha256':sha(FOLDER/'proposals/semantic-index.json'),
                      'source_topics':len(plan['source_topic_inventory'])},sort_keys=True))


if __name__=='__main__':main()
