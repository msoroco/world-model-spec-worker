"""Source-bound tri-state planning model for NRS 484B.210(1) and (4)."""
import hashlib
import json
import math
from pathlib import Path

LAW_SHA='9241d1e338fc52dc9d744182b1535b92bfd064b3be00ddac896b70189ba0bd31'
TEXT_SHA='525f777bf701d9e420e3541071bc6b10de85f747a53fb044431e00826bfee06a'
FEET_200_M=60.96
BOOL_FACTS=('overtakes_on_right','lead_left_turn_or_signal',
    'pavement_unobstructed','no_parked_vehicles','two_lines_each_direction',
    'pavement_unmarked','no_intersection_or_private_way_crossed',
    'one_way_restriction_verified','highway_free_of_obstructions',
    'two_lines_same_direction','authorized_emergency_vehicle',
    'permitted_emergency_vehicle','traffic_incident_management_vehicle',
    'tow_car','coroner_vehicle','public_transit_bus',
    'bus_using_paved_shoulder','lawful_shoulder_signage')

def sha_text(text):return hashlib.sha256(text.encode()).hexdigest()

def source(plan):
    value=json.loads(Path(plan).read_text())
    law=value['source_law']
    if law['sha256']!=LAW_SHA or sha_text(law['text'])!=TEXT_SHA:
        raise ValueError('frozen statutory source hash differs')
    required=(
        'When the driver of the vehicle overtaken is making or signaling to make a left turn.',
        'which is of sufficient width for two or more lines of moving vehicles in each direction.',
        '(1) Except as otherwise provided in subsection 4',
        'does not travel more than 200 feet in the section of pavement not marked as a traffic lane; or (2)',
        'does not travel through an intersection or past any private way',
        'traffic is restricted to one direction of movement',
        'The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to:',
        'where lawfully placed signage allows that vehicle to use the shoulder')
    if not all(piece in law['text'] for piece in required):
        raise ValueError('statutory clause text differs')
    return law

def and3(*values):
    if False in values:return False
    if all(v is True for v in values):return True
    return None

def or3(*values):
    if True in values:return True
    if all(v is False for v in values):return False
    return None

def evaluate(plan,facts):
    law=source(plan)
    if set(facts)!=(set(BOOL_FACTS)|{'unmarked_excursion_m'}):
        raise ValueError('statutory fact coverage differs')
    if any(facts[k] is not None and type(facts[k]) is not bool for k in BOOL_FACTS):
        raise ValueError('statutory boolean fact type')
    distance=facts['unmarked_excursion_m']
    if distance is not None and (type(distance) not in (int,float) or
                                 not math.isfinite(distance) or distance<0):
        raise ValueError('unmarked excursion measurement')
    f=facts
    exempt=or3(f['authorized_emergency_vehicle'],
        f['permitted_emergency_vehicle'],
        f['traffic_incident_management_vehicle'],f['tow_car'],
        f['coroner_vehicle'],
        and3(f['public_transit_bus'],f['bus_using_paved_shoulder'],
             f['lawful_shoulder_signage']))
    c1=or3(None if distance is None else distance<=FEET_200_M,exempt)
    c2=f['no_intersection_or_private_way_crossed']
    branches={
        '1a':f['lead_left_turn_or_signal'],
        '1b':and3(f['pavement_unobstructed'],f['no_parked_vehicles'],
                  f['two_lines_each_direction']),
        '1c':and3(f['pavement_unobstructed'],f['pavement_unmarked'],
                  f['no_parked_vehicles'],or3(c1,c2)),
        '1d':and3(f['one_way_restriction_verified'],
                  f['highway_free_of_obstructions'],
                  f['two_lines_same_direction'])}
    predicate=and3(f['overtakes_on_right'],or3(*branches.values()))
    return {'format':'c146314-statutory-scope-cpu-v1',
        'source_sha256':law['sha256'],'branches':branches,
        'paragraph_c_subcondition_1':c1,'paragraph_c_subcondition_2':c2,
        'subsection_4_c1_exemption':exempt,
        'statutory_permission_predicate':predicate,
        'factual_provenance':'caller_supplied_unverified',
        'legal_verdict':None,'delivery_ready':False}
