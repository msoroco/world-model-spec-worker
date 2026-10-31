"""Four-valued measured expectations, separate from execution and intention.

Uses explicit reference checks, never a generated law or an agent's guess.
Unsupported checks preserve adequate evidence as inconclusive.
"""
import hashlib
import json
from pathlib import Path

VERDICTS = ('compliant', 'violation', 'not applicable', 'inconclusive')
REASONS = ('unresolved_judgment','missing_observations','uncertain_activation','unsupported_reference_check')
LEGACY = {'non_compliant':'violation','not_applicable':'not applicable',None:'inconclusive'}


def normalize(value):
    value = LEGACY.get(value, value)
    if value not in VERDICTS: raise ValueError('Invalid expected verdict: ' + str(value))
    return value


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def intended_outcome(case):
    """Read frozen scenario intent; it never establishes the measured answer."""
    declared=case.get('expected_label_specification',{}).get('intended_outcome')
    if declared:return normalize(declared)
    if case.get('target_type')=='compliant_attempt':return 'compliant'
    if case.get('target_type')=='violating_attempt':return 'violation'
    if case.get('target_law_id')=='NRS-484B-600-1e' and case.get('target_type')=='boundary_probe':
        probe=case.get('probe',{});value=probe.get('test_value')
        unit=probe.get('unit')
        if isinstance(value,(float,int))and not isinstance(value,bool)and unit in ('mph','m/s','mps','km/h','kph'):
            from decimal import Decimal
            v=Decimal(str(value))
            if not v.is_finite():return None
            mps=v*Decimal('.44704')if unit=='mph'else v/Decimal('3.6')if unit in ('km/h','kph')else v
            return 'compliant'if mps<=Decimal('80')*Decimal('.44704')else 'violation'
    return None


def expectation(case, attempt, review, context):
    from expected_labels import rows, sha, load
    attempt=Path(attempt)
    samples=rows(attempt/'trace.jsonl')
    result=load(attempt/'result.json')
    record={'format':'production-verdict-v1','case_id':case['case_id'],
        'target_law_id':case['target_law_id'],'expected_label':'inconclusive',
        'intended_outcome':intended_outcome(case),
        'label_scope':'full_delivered_trace_where_target_rule_applies',
        'scene_assumptions':context,'evidence':{},'missing_evidence':[],
        'inconclusive_reasons':[], 'intention_matched':None,
        'trace_reference':str(attempt/'traffic_spec/trace.json'),
        'trace_sha256':sha(attempt/'traffic_spec/trace.json'),
        'definition_sha256':hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
        'full_recording_window_s':[samples[0]['time_s'],samples[-1]['time_s']] if samples else None,
        'judgment_sweep':case.get('target_type')=='judgment_sweep',
        'evaluation_status':'pending', 'evidence_status':'accepted', 'reference_check':None}
    if not samples or not review.get('trace_integrity_confirmed') or not result.get('maneuver_completed'):
        record.update(evidence_status='needs_repair',inconclusive_reasons=['missing_observations'])
        record['missing_evidence']=['Complete original joined capture and completed maneuver required']
        return record
    if record['judgment_sweep']:
        record.update(evaluation_status='unresolved_judgment',inconclusive_reasons=['unresolved_judgment'])
        return record
    law=case['target_law_id']
    if law == 'NRS-484B-600-1e':
        # Full-trace static statutory cap; samples are actual delivered speeds.
        scenes=load(attempt/'traffic_spec/trace.json')['scenes']
        subject_users=[next((u for u in scene.get('users',[]) if u.get('track')==scene.get('subject')),{}) for scene in scenes]
        motor=all('motor_vehicle' in u.get('classes',[]) for u in subject_users)
        if not motor:
            record.update(inconclusive_reasons=['uncertain_activation'],evaluation_status='pending')
            record['evidence']={'subject_motor_vehicle_confirmed':motor}
            return record
        label,evidence = speed_cap(scenes)
        record.update(expected_label=label,evidence=evidence,
            reference_check={'id':'nrs-484b-600-1e-recorded-cap-v1',
                             'source_sha256':file_hash(__file__),
                             'validation':'tests/test_production.py::ReferenceVerdictTests',
                             'scope':'80 mph cap across all recorded subject samples; no judgment standard'},
            evaluation_status='checked')
        if evidence['missing_scene_indices'] or label=='inconclusive':
            record['expected_label']='inconclusive'
            record.update(evidence_status='needs_repair',inconclusive_reasons=['missing_observations'])
            record['missing_evidence']=['Delivered subject speed unavailable in one or more frames']
    else:
        record['inconclusive_reasons']=['unsupported_reference_check']
    intended=record.get('intended_outcome')
    if intended:
        intended=normalize(intended);record['intended_outcome']=intended
        if record['expected_label'] != 'inconclusive':
            record['intention_matched']=record['expected_label']==intended
            if not record['intention_matched']:record['evidence_status']='needs_repair'
    return record


def speed_cap(scenes, limit_mps=80 * .44704):
    """Explicit sampled convention: every delivered speed <= statutory cap.

    Exact equality remains compliant; no tracking tolerance changes the law.
    A confirmed violation survives missing evidence elsewhere, but recording
    acceptance separately requires the mandatory channel to be complete.
    """
    values=[];missing=[]
    for i,scene in enumerate(scenes):
        user=next((u for u in scene.get('users',[]) if u.get('track')==scene.get('subject')),None)
        value=user.get('kin',{}).get('speed') if user else None
        import math
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value < 0:
            missing.append(i)
        else:values.append((i,value))
    exceeded=[i for i,v in values if v>limit_mps]
    verdict='violation' if exceeded else 'inconclusive' if missing or not values else 'compliant'
    return verdict, {'limit_mps':limit_mps,'comparison':'<=','sampling':'every delivered subject sample',
        'exceedance_scene_indices':exceeded,'missing_scene_indices':missing,
        'minimum_mps':min((v for _,v in values),default=None),'maximum_mps':max((v for _,v in values),default=None)}


def validate(record):
    if record.get('expected_label') not in VERDICTS:raise ValueError('Invalid four-valued verdict')
    reasons=record.get('inconclusive_reasons',[])
    if any(r not in REASONS for r in reasons):raise ValueError('Invalid inconclusive reason')
    if record['expected_label']=='inconclusive' and not reasons:raise ValueError('Inconclusive requires a reason')
    if record['expected_label']!='inconclusive' and reasons:raise ValueError('Resolved verdict carries inconclusive reasons')
    if record['expected_label']!='inconclusive' and not record.get('reference_check'):
        raise ValueError('Resolved verdict needs a reference check')
    return record
