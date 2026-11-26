"""Author canonical parking stage proposals from the frozen assignment and cases."""
import hashlib
import json
from pathlib import Path
import sys

PKG=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PKG))
from parking_scene import CASES,request

A=PKG.name
assignment=json.loads((Path('inputs')/A/'assignment.json').read_text())
LAW=assignment['law_id'];CELL=assignment['cell_id'];ACTOR=assignment['actor']
QUOTE=assignment['law']['text']
TEMPLATE=LAW+'@'+ACTOR
P=PKG/'proposals';P.mkdir(exist_ok=True)


def write(name,value):
    path=P/(name+'.json');path.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':str(path.relative_to(PKG)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance={'actor':ACTOR,'cell_id':CELL,'status':'draft',
      'relevant_laws':[{'law_id':LAW,'quote':QUOTE,'applies_to':[ACTOR],
        'relevance_type':'direct','confidence':'high',
        'notes':'Frozen one-way highway parallel parking cell with adjacent curbs; ordinance/DOT applicability remains source dependent.'}],
      'borderline_excluded':[]}
    refs={'relevance_batch':write('relevance-batch',relevance),'relevance':write('relevance',relevance)}
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'quote':QUOTE,'status':'draft',
      'structure':{'activation':{'description':'Vehicle stopped or parked on a highway with adjacent curbs',
                    'source_clause':'every vehicle stopped or parked upon a highway where there are adjacent curbs'},
       'obligation':{'description':'Right-hand wheels parallel to and within 18 inches of right-hand curb',
                     'type':'must','source_clause':'right-hand wheels of the vehicle parallel to and within 18 inches of the right-hand curb',
                     'numeric_conditions':[{'variable':'observed_right_wheel_curb_gap_in','operator':'<=','value':18,'unit':'in'}]},
       'exceptions':[{'description':'Local ordinance may permit left-hand wheels within 18 inches of left-hand curb of one-way highway',
                      'source_clause':'Local authorities may by ordinance permit parking of vehicles with the left-hand wheels adjacent to and within 18 inches of the left-hand curb of a one-way highway'},
                     {'description':'Local ordinance may permit angle parking; DOT-maintained highway also requires Department width determination',
                      'source_clause':'Local authorities may by ordinance permit angle parking on any highway, except that angle parking must not be permitted on any highway constructed and maintained by the Department of Transportation under the authority granted by chapter 408 of NRS unless the Department has determined that the highway is of sufficient width to permit angle parking without interfering with the free movement of traffic.'}],
       'timing':{'description':'Throughout observed stopped or parked interval'},
       'judgment_calls_needed':[]},
      'parameter_refs':[{'name':'requested_wheel_curb_gap_in','kind':'controller','range_or_domain':[16,18,20]},
                        {'name':'parking_kind','kind':'world_setup','range_or_domain':list({v[0] for v in CASES.values()})},
                        {'name':'rest_mode','kind':'controller','range_or_domain':['stopped','parked']}]}
    refs['template']=write('template',template)
    refs['judgment_observables']=[]
    bindings={'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'established_contexts':[{'name':'one_way_parallel_parking','source':'frozen C149985 catalog cell and law'}],
      'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
      'context_refs':[],'fixed_parameters':[],
      'variable_parameters':[{'name':'requested_wheel_curb_gap_in','kind':'controller',
          'range_or_domain':[16,18,20],'used_by_laws':[LAW]},
         {'name':'parking_kind','kind':'world_setup','range_or_domain':'default right, left ordinance, ordinary angle, DOT angle','used_by_laws':[LAW]},
         {'name':'rest_mode','kind':'controller','range_or_domain':['stopped','parked'],'used_by_laws':[LAW]}]}
    refs['bindings']=write('bindings',bindings)
    base_construction=json.loads((PKG/'native'/'bundles'/'right_18_parked'/'construction.json').read_text())
    cases=[{'case_id':A+'__baseline','target_law_id':None,'target_type':'baseline',
        'rationale':'Unselected neutral one-way parking definition; no legal outcome asserted.',
        'recording_description':base_construction['recording_description'],
        'unresolved_judgment_calls':[],
        'variable_assignments':{'requested_wheel_curb_gap_in':{'kind':'controller','unit':'in','value':18},
          'parking_kind':{'kind':'world_setup','unit':'category','value':'default_right'},
          'rest_mode':{'kind':'controller','unit':'category','value':'parked'}}}]
    for suffix,(kind,gap,heading,rest) in CASES.items():
        cid=A+'__'+suffix
        construction=json.loads((PKG/'native'/'bundles'/suffix/'construction.json').read_text())
        cases.append({'case_id':cid,'target_law_id':LAW,
            'target_type':'boundary_probe' if suffix.startswith('right_') else 'compliant_attempt',
            'probe':{'primary_variable':'requested_wheel_curb_gap_in' if suffix.startswith('right_') else 'parking_kind',
                'comparison_or_standard':'18-inch statutory wheel-to-curb boundary or conditional exception',
                'target_value_or_branch':gap if suffix.startswith('right_') else kind,
                **({'threshold_ref':'obligation.numeric_conditions[0]',
                    'operator':'<=','unit':'in','test_value':gap}
                    if suffix.startswith('right_') else {})},
            'paired_probe_id':'C149985-right-curb' if suffix.startswith('right_') else 'C149985-exception',
            **({'epsilon_used':2} if suffix.startswith('right_') else {}),
            'deliberate_differences':(['rest_mode'] if suffix=='right_18_stopped' else
                                      ['requested_wheel_curb_gap_in'] if suffix.startswith('right_') else
                                      ['parking_kind']),
            'rationale':'Original stopped/parked, curb and wheel source measured; local ordinance and DOT authority remain independent source facts.',
            'recording_description':construction['recording_description'],
            'unresolved_judgment_calls':[],
            'variable_assignments':{'requested_wheel_curb_gap_in':{'kind':'controller','unit':'in','value':gap},
                'parking_kind':{'kind':'world_setup','unit':'category','value':kind},
                'rest_mode':{'kind':'controller','unit':'category','value':rest}}})
    proposal={'actor':ACTOR,'cell_id':CELL,'status':'draft','sweeps_expanded':True,
              'cases':cases,'semantic_status':'draft','sweep_specs':[]}
    refs['cases']=write('cases',proposal)
    index={'assignment_id':A,'format':'worker-semantic-delivery','stages':refs}
    (P/'semantic-index.json').write_text(json.dumps(index,indent=2)+'\n')
    return {'cases':len(cases),'index_sha256':hashlib.sha256((P/'semantic-index.json').read_bytes()).hexdigest()}


if __name__=='__main__':print(json.dumps(main(),indent=2))
