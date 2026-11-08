"""Independently recompute C146314 statutory CPU truth-table proof."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def AND(*values):
    if any(x is False for x in values):return False
    if all(x is True for x in values):return True
    return None
def OR(*values):
    if any(x is True for x in values):return True
    if all(x is False for x in values):return False
    return None

def audit():
    plan=read(CASE/'case-plan.json');proof=read(CASE/'native/statutory-proof.json')
    law=plan['source_law'];text=law['text']
    require(law['sha256']==proof['declared_source_sha256']==
            '9241d1e338fc52dc9d744182b1535b92bfd064b3be00ddac896b70189ba0bd31' and
            hashlib.sha256(text.encode()).hexdigest()==
            '525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a' and
            proof['paragraph_c_alternatives_joined_by_or'] is True and
            proof['subsection_4_exemption_only_paragraph_c_1'] is True and
            len(proof['cases'])==13 and
            set(proof['negatives'])=={'altered_source','missing_fact',
                'invalid_distance','invalid_boolean'} and
            proof['legal_verdict'] is None and
            proof['delivery_ready'] is False,
            'source/proof binding')
    names={row['name'] for row in proof['cases']}
    require(names=={'a_left_signal','b_wide_clear','c_under_200ft',
        'c_exact_200ft','c_over_200ft','c_second_alternative','c_exempt_tow',
        'c_bus_without_sign','c_bus_with_sign','d_one_way_clear','d_obstructed',
        'inactive_activation','unknown_one_way'},'truth table coverage')
    for row in proof['cases']:
        f=row['inputs']
        exemption=OR(f['authorized_emergency_vehicle'],
            f['permitted_emergency_vehicle'],
            f['traffic_incident_management_vehicle'],f['tow_car'],
            f['coroner_vehicle'],AND(f['public_transit_bus'],
                f['bus_using_paved_shoulder'],f['lawful_shoulder_signage']))
        c1=OR(None if f['unmarked_excursion_m'] is None else
              f['unmarked_excursion_m']<=60.96,exemption)
        branches={
            '1a':f['lead_left_turn_or_signal'],
            '1b':AND(f['pavement_unobstructed'],f['no_parked_vehicles'],
                     f['two_lines_each_direction']),
            '1c':AND(f['pavement_unobstructed'],f['pavement_unmarked'],
                     f['no_parked_vehicles'],
                     OR(c1,f['no_intersection_or_private_way_crossed'])),
            '1d':AND(f['one_way_restriction_verified'],
                     f['highway_free_of_obstructions'],
                     f['two_lines_same_direction'])}
        permission=AND(f['overtakes_on_right'],OR(*branches.values()))
        require(row['actual_branches']==branches and
                row['actual'] is branches[row['branch']] and
                row['expected'] is branches[row['branch']] and
                row['permission_predicate'] is permission,
                'independent statutory recomputation '+row['name'])
    summary=plan['requirement_dispositions'][3]['branch']
    require('and crosses no intersection' in summary and
            'traffic lane; or (2)' in text,
            'recovered summary/source divergence')
    result={'format':'c146314-independent-statutory-scope-audit-v1',
        'truth_table_rows':13,'negative_controls':4,
        'source_summary_conjunction_disagrees_with_source_or':True,
        'original_fact_provenance_verified':False,
        'legal_verdict':None,'delivery_ready':False}
    (CASE/'native/statutory-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
