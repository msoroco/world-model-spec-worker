"""Exercise the exact-source statutory predicate, boundaries and negative controls."""
import json
from pathlib import Path
import tempfile

from statutory_scope import BOOL_FACTS, evaluate, source

CASE=Path(__file__).resolve().parent.parent
PLAN=CASE/'case-plan.json'

def facts(**changes):
    result={key:False for key in BOOL_FACTS}
    result['unmarked_excursion_m']=61.01
    result['overtakes_on_right']=True
    result.update(changes)
    return result

def run():
    law=source(PLAN)
    cases=(
        ('a_left_signal',facts(lead_left_turn_or_signal=True),'1a',True),
        ('b_wide_clear',facts(pavement_unobstructed=True,
            no_parked_vehicles=True,two_lines_each_direction=True),'1b',True),
        ('c_under_200ft',facts(pavement_unobstructed=True,pavement_unmarked=True,
            no_parked_vehicles=True,unmarked_excursion_m=60.95),'1c',True),
        ('c_exact_200ft',facts(pavement_unobstructed=True,pavement_unmarked=True,
            no_parked_vehicles=True,unmarked_excursion_m=60.96),'1c',True),
        ('c_over_200ft',facts(pavement_unobstructed=True,pavement_unmarked=True,
            no_parked_vehicles=True,unmarked_excursion_m=60.97),'1c',False),
        ('c_second_alternative',facts(pavement_unobstructed=True,
            pavement_unmarked=True,no_parked_vehicles=True,
            no_intersection_or_private_way_crossed=True),'1c',True),
        ('c_exempt_tow',facts(pavement_unobstructed=True,
            pavement_unmarked=True,no_parked_vehicles=True,tow_car=True),'1c',True),
        ('c_bus_without_sign',facts(pavement_unobstructed=True,
            pavement_unmarked=True,no_parked_vehicles=True,public_transit_bus=True,
            bus_using_paved_shoulder=True),'1c',False),
        ('c_bus_with_sign',facts(pavement_unobstructed=True,
            pavement_unmarked=True,no_parked_vehicles=True,public_transit_bus=True,
            bus_using_paved_shoulder=True,lawful_shoulder_signage=True),'1c',True),
        ('d_one_way_clear',facts(one_way_restriction_verified=True,
            highway_free_of_obstructions=True,two_lines_same_direction=True),'1d',True),
        ('d_obstructed',facts(one_way_restriction_verified=True,
            highway_free_of_obstructions=False,two_lines_same_direction=True),'1d',False),
        ('inactive_activation',facts(overtakes_on_right=False,
            lead_left_turn_or_signal=True),'1a',True),
        ('unknown_one_way',facts(one_way_restriction_verified=None,
            highway_free_of_obstructions=True,two_lines_same_direction=True),'1d',None),
    )
    results=[]
    for name,inputs,branch,expected in cases:
        actual=evaluate(PLAN,inputs)
        if (actual['branches'][branch] is not expected or
                actual['legal_verdict'] is not None):
            raise AssertionError('statutory branch differs: '+name)
        if name=='inactive_activation' and actual['statutory_permission_predicate'] is not False:
            raise AssertionError('activation not applied')
        if name=='unknown_one_way' and actual['statutory_permission_predicate'] is not None:
            raise AssertionError('unknown fact promoted')
        results.append({'name':name,'inputs':inputs,'branch':branch,'expected':expected,
                        'actual':actual['branches'][branch],
                        'actual_branches':actual['branches'],
                        'permission_predicate':actual['statutory_permission_predicate']})
    negatives=[]
    for kind in ('altered_source','missing_fact','invalid_distance','invalid_boolean'):
        try:
            if kind=='altered_source':
                with tempfile.TemporaryDirectory() as folder:
                    plan=Path(folder)/'plan.json';value=json.loads(PLAN.read_text())
                    value['source_law']['text']+=' changed'
                    plan.write_text(json.dumps(value))
                    evaluate(plan,facts())
            elif kind=='missing_fact':
                value=facts();del value['overtakes_on_right'];evaluate(PLAN,value)
            elif kind=='invalid_distance':
                evaluate(PLAN,facts(unmarked_excursion_m=float('nan')))
            else:evaluate(PLAN,facts(tow_car='yes'))
        except ValueError: negatives.append(kind)
        else:raise AssertionError('statutory negative accepted: '+kind)
    summary=json.loads(PLAN.read_text())['source_law']['text']
    receipt={'format':'c146314-statutory-scope-proof-v1',
        'declared_source_sha256':law['sha256'],
        'paragraph_c_alternatives_joined_by_or':
            'traffic lane; or (2)' in summary,
        'subsection_4_exemption_only_paragraph_c_1':
            'subparagraph (1) of paragraph (c) of subsection 1' in summary,
        'cases':results,'negatives':negatives,
        'legal_verdict':None,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'native/statutory-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    r=run();print(json.dumps({'positives':len(r['cases']),
                              'negatives':len(r['negatives'])}))
