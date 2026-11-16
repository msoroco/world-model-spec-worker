"""Independent exact-law review of the planned red-curb exception matrix."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def require(ok, message):
    if not ok:raise ValueError(message)

def audit(matrix):
    source=REPO/'inputs'/ROOT.name/'assignment.json'
    law=json.loads(source.read_text())['law']['text']
    require(matrix['assignment_id']==ROOT.name and
            matrix['assignment_source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest() and
            matrix['law_text_sha256']==hashlib.sha256(law.encode()).hexdigest(),
            'Frozen law source changed')
    cases={row['case_id']:row for row in matrix['cases']}
    require(len(cases)==28 and len(matrix['cases'])==28 and
            len(matrix['comparisons'])==17, 'Exception branch count changed')
    require(all(row['status']=='planned_unverified' and
                row['observed_duration_s'] is None and row['legal_verdict'] is None and
                row['paint']=='red' and row['target_x_m']==40 for row in cases.values()),
            'Planning data claims observation or legal outcome')
    for service,topic in [('tour_bus','text-4'),('shuttle_bus','text-4'),
                          ('limo','text-4'),('rtc_bus','text-5')]:
        rows={label:cases[ROOT.name+'__'+service+'_'+label] for label in
              ('below','at','above','no_loading')}
        require([rows[label]['requested_stationary_duration_s'] for label in
                 ('below','at','above')]==[1799.95,1800,1800.05],
                'Thirty-minute boundary missing: '+service)
        require(all(topic in row['source_topic_ids'] and
                    row['service_class']==service and row['sign_classes']
                    for row in rows.values()),'Signed service context missing: '+service)
        require(all(rows[label]['activity_request']=='passenger_loading' for label in
                    ('below','at','above')) and
                rows['no_loading']['activity_request'] is None,
                'Passenger-loading purpose contrast missing: '+service)
    for service in ('armored_car','emergency_vehicle'):
        for signed in ('signed','unsigned'):
            for activity in ('business','no_business'):
                row=cases[ROOT.name+'__'+service+'_'+signed+'_'+activity]
                require(row['service_class']==service and 'text-6' in row['source_topic_ids'] and
                        bool(row['sign_classes'])==(signed=='signed') and
                        bool(row['activity_request'])==(activity=='business'),
                        'Necessary-business factor missing: '+service)
    for suffix in ('mail_adjacent_deposit','mail_no_box_deposit',
                   'mail_adjacent_no_deposit'):
        row=cases[ROOT.name+'__'+suffix]
        require(set(('text-7','text-8'))<=set(row['source_topic_ids']),
                'Split mail clause not joined')
    require(cases[ROOT.name+'__mail_adjacent_deposit']['mailbox_requested'] and
            not cases[ROOT.name+'__mail_no_box_deposit']['mailbox_requested'] and
            cases[ROOT.name+'__mail_adjacent_no_deposit']['activity_request'] is None,
            'Mail adjacency/activity probes missing')
    comparison_ids=set()
    for row in matrix['comparisons']:
        require(row['comparison_id'] not in comparison_ids and
                row['status']=='planned_unverified' and
                len(row['case_ids'])>=2 and
                all(cid in cases or cid==ROOT.name+'__reference' for cid in row['case_ids']) and
                row['deliberate_differences'] and row['fixed_conditions'],
                'Incomplete controlled comparison')
        comparison_ids.add(row['comparison_id'])
    used={cid for row in matrix['comparisons'] for cid in row['case_ids']}
    require(set(cases)<=used,'Uncompared exception case')
    return {'format':'c150142-exception-matrix-audit-v1','passed':True,
            'planned_cases':len(cases),'comparisons':len(comparison_ids),
            'original_native_observed':False,'legal_verdict':None}

if __name__=='__main__':
    matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
    print(json.dumps(audit(matrix),sort_keys=True))
