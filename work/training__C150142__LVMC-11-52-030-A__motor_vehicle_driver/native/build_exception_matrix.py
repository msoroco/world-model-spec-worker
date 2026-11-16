"""Enumerate exact LVMC red-curb exception probes without legal labels."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW_SOURCE = REPO/'inputs'/ASSIGNMENT/'assignment.json'


def build():
    assignment = json.loads(LAW_SOURCE.read_text())
    if assignment['law_id'] != 'LVMC-11-52-030-A' or assignment['cell_id'] != 'C150142':
        raise ValueError('Frozen law/cell identity changed')
    law = assignment['law']['text']
    required = ('thirty minutes', 'Armored cars and emergency vehicles',
                'drop box for U.S. mail')
    if any(fragment not in law for fragment in required):
        raise ValueError('Exception text changed')
    cases = []
    comparisons = []

    def add(suffix, branch, service, sign, duration, activity,
            mailbox=False, topic_ids=()):
        case = {'case_id': ASSIGNMENT+'__'+suffix,
                'branch': branch, 'source_topic_ids': list(topic_ids),
                'service_class': service, 'sign_classes': list(sign),
                'requested_stationary_duration_s': duration,
                'activity_request': activity,
                'mailbox_requested': mailbox,
                'paint': 'red', 'target_x_m': 40,
                'status': 'planned_unverified',
                'observed_duration_s': None,
                'legal_verdict': None}
        cases.append(case)
        return case['case_id']

    def pair(suffix, branch, members, variable, fixed):
        comparisons.append({'comparison_id': ASSIGNMENT+'__'+suffix,
                            'branch': branch, 'case_ids': members,
                            'deliberate_differences': list(variable),
                            'fixed_conditions': list(fixed),
                            'status': 'planned_unverified'})

    ordinary_signed = add('ordinary_red_signed', 'red_with_or_without_sign',
                          'ordinary', ('no_parking',), 12, None,
                          topic_ids=('text-2','text-3'))
    pair('ordinary_sign_pair', 'red_with_or_without_sign',
         [ASSIGNMENT+'__reference', ordinary_signed],
         ('sign_present',), ('red paint','ordinary vehicle','parking target',
                            'controller','camera profile'))

    for service, sign_classes, topic in (
            ('tour_bus', ('tour_bus','shuttle_bus','limo'), 'text-4'),
            ('shuttle_bus', ('tour_bus','shuttle_bus','limo'), 'text-4'),
            ('limo', ('tour_bus','shuttle_bus','limo'), 'text-4'),
            ('rtc_bus', ('rtc_bus',), 'text-5')):
        ids = {}
        for label, duration in (('below',1799.95),('at',1800),('above',1800.05)):
            ids[label] = add(service+'_'+label, 'signed_passenger_loading',
                             service, sign_classes, duration, 'passenger_loading',
                             topic_ids=(topic,))
        ids['no_loading'] = add(service+'_no_loading', 'signed_passenger_loading',
                                service, sign_classes, 1800, None,
                                topic_ids=(topic,))
        fixed = ('red paint','sign text','vehicle service class',
                 'parking target','camera profile','passenger loading')
        pair(service+'_30min_boundary', 'signed_passenger_loading',
             [ids['below'],ids['at'],ids['above']],
             ('stationary_duration_s',), fixed)
        pair(service+'_loading_purpose', 'signed_passenger_loading',
             [ids['at'],ids['no_loading']], ('passenger_loading_event',),
             ('red paint','sign text','vehicle service class',
              'stationary duration','parking target','camera profile'))

    for service in ('armored_car','emergency_vehicle'):
        ids={}
        for signed in (False,True):
            for business in (False,True):
                suffix=service+('_signed' if signed else '_unsigned')+\
                    ('_business' if business else '_no_business')
                ids[(signed,business)] = add(suffix,'necessary_business',service,
                    ('armored_or_emergency',) if signed else (),12,
                    'business_activity' if business else None,
                    topic_ids=('text-6',))
        pair(service+'_sign_exception','necessary_business',
             [ids[(False,True)],ids[(True,True)]],('sign_present',),
             ('red paint','service class','business activity','duration',
              'parking target','camera profile'))
        for signed in (False,True):
            pair(service+('_signed' if signed else '_unsigned')+'_business_pair',
                 'necessary_business',
                 [ids[(signed,True)],ids[(signed,False)]],
                 ('business_activity_event',),
                 ('red paint','service class','sign state','duration',
                  'parking target','camera profile'))

    adjacent=add('mail_adjacent_deposit','mail_drop', 'ordinary',(),12,
                 'mail_deposit',True,('text-7','text-8'))
    absent=add('mail_no_box_deposit','mail_drop','ordinary',(),12,
               'mail_deposit',False,('text-7','text-8'))
    no_deposit=add('mail_adjacent_no_deposit','mail_drop','ordinary',(),12,
                   None,True,('text-7','text-8'))
    pair('mailbox_adjacency','mail_drop',[adjacent,absent],
         ('mailbox_presence',),('red paint','ordinary vehicle','stop duration',
                                'parking target','camera profile'))
    pair('mail_activity','mail_drop',[adjacent,no_deposit],
         ('mail_deposit_event',),('red paint','ordinary vehicle',
                                'mailbox geometry','stop duration',
                                'parking target','camera profile'))
    matrix={'format':'c150142-exception-case-matrix-v1',
            'assignment_id':ASSIGNMENT,
            'assignment_source_sha256':hashlib.sha256(LAW_SOURCE.read_bytes()).hexdigest(),
            'law_text_sha256':hashlib.sha256(law.encode()).hexdigest(),
            'cases':cases,'comparisons':comparisons,
            'status':'planned_unverified',
            'original_native_observed':False,
            'legal_verdict':None}
    output=ROOT/'exception-case-matrix.json'
    output.write_text(json.dumps(matrix,indent=2,allow_nan=False)+'\n')
    return {'cases':len(cases),'comparisons':len(comparisons),
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
