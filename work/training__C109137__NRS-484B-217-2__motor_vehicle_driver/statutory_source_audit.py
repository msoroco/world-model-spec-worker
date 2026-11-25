"""Independent source-only audit of the two NRS 484B.217 crossing exceptions."""
import argparse
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CROSSING = runpy.run_path(str(HERE / 'prove-selected-crossing-pair.py'))
TRAFFIC = runpy.run_path(str(HERE / 'native/zone/audit_traffic_sources.py'))
PREFIX = {'probe_1': 'selected-probe1', 'probe_2': 'selected-probe2',
          'traffic_clear_traffic': 'selected-traffic-clear_traffic',
          'traffic_following_brake': 'selected-traffic-following_brake'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(claim_accepted=False):
    if claim_accepted:
        raise ValueError('Original zone, NRS 484B.413 signal compliance, safe turn and no-impediment review required')
    assignment = read(ROOT / 'inputs' / HERE.name / 'assignment.json')
    plan = read(HERE / 'case-plan.json')
    law = assignment['law']['text']
    if (plan['source_law']['text'] != law or
            'A driver may drive across a pavement striping marking such zone to an adjoining highway' not in law or
            'in compliance with NRS 484B.413' not in law):
        raise ValueError('Exact subsection 3/4 source text changed')
    cases = [c['case_id'] for c in plan['cases']]
    for index in (1, 2):
        d = plan['requirement_dispositions'][index]
        if d['status'] != 'selected_required' or d['case_ids'] != cases:
            raise ValueError('Statutory alternative lacks exact same-cell case mapping')
    records = []
    for suffix, prefix in PREFIX.items():
        fixture = HERE / (prefix + '-fixture')
        raw, frames, review = (fixture / name for name in
                              ('native-raw-actors.jsonl', 'video_frames.jsonl', 'review.json'))
        case_id = HERE.name + '__' + suffix
        if suffix.startswith('traffic_'):
            observed = TRAFFIC['measure'](raw, frames, review)
        else:
            observed = CROSSING['events'](raw, frames)
        public_path = HERE / (prefix + '-compatibility.json')
        saved_path = HERE / (prefix + '-processing.json')
        public, saved = read(public_path), read(saved_path)
        if (not public['passed'] or not saved['passed'] or not saved['recorded_only'] or
                public['case_id'] != case_id or saved['case_id'] != case_id or
                public['candidate_id'] != 'primary' or saved['candidate_id'] != 'primary' or
                saved['timestamp_joins'].get('frames') != 600 or
                set(public['measurement_examples']) !=
                    ({'traffic_response','subsection3_adjoining','subsection4_left_turn'}
                     if suffix.startswith('traffic_') else
                     {'adjoining_crossing','subsection3_adjoining','subsection4_left_turn'})):
            raise ValueError('Current-runtime selected source/measurement missing: ' + suffix)
        for key in ('subsection3_adjoining', 'subsection4_left_turn'):
            item = public['measurement_examples'][key]
            value = item['value']
            if (item['sources']['native-raw-actors.jsonl'] != sha(raw) or
                    item['sources']['video_frames.jsonl'] != sha(frames) or
                    item['sources']['review.json'] != sha(review) or
                    value['first_stripe_body_frame'] != observed['first_stripe_body_frame'] or
                    value['first_adjoining_road_frame'] != observed['first_adjoining_road_frame'] or
                    value['first_left_indicator_frame'] != observed['first_left_indicator_frame'] or
                    value['no_impediment_legally_established'] is not False):
                raise ValueError('Subsection source, crossing or legal flag differs: ' + suffix)
        if (public['measurement_examples']['subsection3_adjoining']['value']['appropriate_signal_legally_verified'] is not False or
                public['measurement_examples']['subsection4_left_turn']['value']['nrs_484b_413_compliance_verified'] is not False or
                public['measurement_examples']['subsection4_left_turn']['value']['safe_turn_legally_established'] is not False):
            raise ValueError('Unreviewed signal or safety was asserted')
        records.append({'case_id':case_id,'source_sha256':{'actors':sha(raw),'frames':sha(frames),'review':sha(review)},
                        'observed_crossing':{key:observed[key] for key in ('first_stripe_body_frame','first_adjoining_road_frame','first_left_indicator_frame')},
                        'compatibility_sha256':sha(public_path),'saved_processing_sha256':sha(saved_path)})
    return {'format':'c109137-statutory-source-audit-v1','passed':True,'case_count':4,
            'law_text_sha256':hashlib.sha256(law.encode()).hexdigest(),
            'official_source':'https://www.leg.state.nv.us/nrs/NRS-484B.html',
            'subsection3':'adjoining-highway crossing observed; signal and no impediment require original review',
            'subsection4':'left-turn crossing observed; NRS 484B.413 compliance, safety and no impediment require original review',
            'records':records,'source_only':True,'original_native_observed':False,
            'physical_or_legal_acceptance':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--claim-accepted', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.claim_accepted)
    if args.output:
        args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':result['passed'],'case_count':result['case_count']}))
