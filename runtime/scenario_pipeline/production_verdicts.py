"""Four-valued measured expectations, separate from execution and intention.

Uses explicit reference checks, never a generated law or an agent's guess.
Unavailable outcomes remain null with independent processing reasons.
"""
import hashlib
import json
from pathlib import Path

VERDICTS = ('compliant', 'violation', 'not applicable', 'judgment call')
LEGACY = {'non_compliant':'violation','not_applicable':'not applicable'}


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


def _measured_expectation(case, attempt, review, context):
    from expected_labels import rows, sha, load
    attempt=Path(attempt)
    samples=rows(attempt/'trace.jsonl')
    result=load(attempt/'result.json')
    record={'case_id':case['case_id'],
        'target_law_id':case['target_law_id'],'expected_label':None,
        'intended_outcome':intended_outcome(case),
        'label_scope':'full_delivered_trace_where_target_rule_applies',
        'scene_assumptions':context,'evidence':{},'missing_evidence':[],
        'processing_reasons':[], 'intention_matched':None,
        'trace_reference':str(attempt/'traffic_spec/trace.json'),
        'trace_sha256':sha(attempt/'traffic_spec/trace.json'),
        'definition_sha256':hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
        'full_recording_window_s':[samples[0]['time_s'],samples[-1]['time_s']] if samples else None,
        'judgment_sweep':case.get('target_type')=='judgment_sweep',
        'evaluation_status':'pending', 'evidence_status':'accepted', 'reference_check':None}
    if not samples or not review.get('trace_integrity_confirmed') or not result.get('maneuver_completed'):
        record.update(evidence_status='needs_repair',processing_reasons=['missing_observations'])
        record['missing_evidence']=['Complete original joined capture and completed maneuver required']
        return record
    if case.get('unresolved_judgment_calls'):
        record.update(evaluation_status='legal_judgment')
        return record
    law=case['target_law_id']
    if law == 'NRS-484B-600-1e':
        # Full-trace static statutory cap; samples are actual delivered speeds.
        scenes=load(attempt/'traffic_spec/trace.json')['scenes']
        subject_users=[next((u for u in scene.get('users',[]) if u.get('track')==scene.get('subject')),{}) for scene in scenes]
        motor=bool(subject_users) and all('motor_vehicle' in u.get('classes',[]) for u in subject_users)
        if not motor:
            record.update(processing_reasons=['uncertain_applicability'],evaluation_status='pending')
            record['evidence']={'subject_motor_vehicle_confirmed':motor}
            return record
        label,evidence = speed_cap(scenes)
        record.update(expected_label=label,evidence=evidence,
            reference_check={'id':'nrs-484b-600-1e-recorded-cap-v1',
                             'validation':'tests/test_production.py::ReferenceVerdictTests',
                             'scope':'80 mph cap across all recorded subject samples; no judgment standard'},
            evaluation_status='checked')
        if evidence['missing_scene_indices'] or label is None:
            record['expected_label']=None
            record.update(evidence_status='needs_repair',processing_reasons=['missing_observations'])
            record['missing_evidence']=['Delivered subject speed unavailable in one or more frames']
    else:
        record['processing_reasons']=['unsupported_evaluation']
    intended=record.get('intended_outcome')
    if intended:
        intended=normalize(intended);record['intended_outcome']=intended
        if record['expected_label'] in VERDICTS[:3]:
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
    verdict='violation' if exceeded else None if missing or not values else 'compliant'
    return verdict, {'limit_mps':limit_mps,'comparison':'<=','sampling':'every delivered subject sample',
        'exceedance_scene_indices':exceeded,'missing_scene_indices':missing,
        'minimum_mps':min((v for _,v in values),default=None),'maximum_mps':max((v for _,v in values),default=None)}


def validate(record):
    return validate_authoritative(record)


# The authoritative delivery contract. Legacy input records must be classified
# against their frozen definition; neither a null label nor a sweep proves a
# legal judgment call. Consumers migrate together before v2 publication.
AUTHORITATIVE_FORMAT = 'production-verdict-v2'
OUTCOMES = VERDICTS
PROCESSING_REASONS = frozenset(('missing_observations', 'uncertain_applicability',
                              'unsupported_evaluation', 'unresolved_source'))
PRESENTATION_FIELDS = ('format', 'case_id', 'target_law_id', 'recording_identity',
                      'expected_label', 'processing_reasons', 'evidence_status',
                      'evaluation_status', 'legal_judgment', 'sweep_membership',
                      'source_signature', 'classification_method', 'evaluation_method')


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def assessment_reference(reference):
    """Keep the assessment basis, not bookkeeping about its generator.

    A method ID, scope, measured facts and written assessment explain a label.
    A script location or implementation checksum does not establish that label
    and must never require retaining one-time preparation code.
    """
    from copy import deepcopy
    if reference is None:
        return None
    if not isinstance(reference, dict):
        raise ValueError('Assessment reference must describe its method and evidence')
    result = deepcopy(reference)
    for key in ('source_path', 'source_sha256', 'authority_builder'):
        result.pop(key, None)
    implementations = result.get('source_hashes')
    if isinstance(implementations, dict):
        retained = {name: value for name, value in implementations.items()
                    if Path(name).suffix not in ('.py', '.pyc', '.sh')}
        if retained:
            result['source_hashes'] = retained
        else:
            result.pop('source_hashes')
    return result


def source_signature(record):
    return canonical_hash({key: record.get(key) for key in
        ('case_id', 'target_law_id', 'recording_identity', 'source_hashes',
         'expected_label', 'processing_reasons', 'evidence_status',
         'evaluation_status', 'legal_judgment', 'sweep_membership',
         'classification_method', 'reference_check', 'evidence',
         'scene_assumptions', 'label_scope', 'full_recording_window_s',
         'intended_outcome', 'intention_matched', 'evaluation_method')})


def _independent_violation(record, references, outcome):
    """Retain unresolved terms when a different, evidenced duty is breached.

    The source assessment must name its facts and explicitly establish that
    deciding those terms is unnecessary. Merely requesting a violation does
    not override authored legal uncertainty.
    """
    reference = record.get('reference_check') or {}
    if not isinstance(reference, dict):
        raise ValueError('Assessment reference must describe its method and evidence')
    assessment = reference.get('independent_violation')
    if assessment is None:
        return False
    if outcome != 'violation' or not references or not isinstance(assessment, dict):
        raise ValueError('Independent breach requires a violation with unresolved legal terms')
    requirement = assessment.get('requirement')
    evidence_key = assessment.get('evidence_key')
    evidence = record.get('evidence', {})
    phrases = sorted({ref['phrase'] for ref in references})
    if (not isinstance(requirement, str) or not requirement.strip() or
            not isinstance(evidence_key, str) or not isinstance(evidence, dict) or
            not isinstance(evidence.get(evidence_key), dict) or not evidence[evidence_key] or
            assessment.get('independent_of_phrases') != phrases):
        raise ValueError('Independent breach requires named facts and every nondecisive legal term')
    return True


def authoritative_record(case, measured, *, recording_identity, source_hashes):
    """Classify source-bound measured results; never infer meaning from names.

    Existing reference evaluators supply measured outcomes and evidence. This
    function owns only the shared outcome/status/sweep/legal classification.
    It also serves saved reconstruction when supplied the same frozen inputs.
    """
    from copy import deepcopy
    record = deepcopy(measured)
    if record.get('case_id') != case.get('case_id') or record.get('target_law_id') != case.get('target_law_id'):
        raise ValueError('Label record disagrees with frozen case/law identity')
    reasons = set(record.get('processing_reasons', []))
    legacy_reasons = {'missing_observations': 'missing_observations',
                      'uncertain_activation': 'uncertain_applicability',
                      'unsupported_reference_check': 'unsupported_evaluation'}
    for reason in record.pop('inconclusive_reasons', []):
        if reason in legacy_reasons:
            reasons.add(legacy_reasons[reason])
        elif reason != 'unresolved_judgment':
            raise ValueError('Unsupported legacy processing reason: ' + str(reason))
    outcome = record.get('expected_label')
    if outcome in ('non_compliant', 'not_applicable'):
        outcome = {'non_compliant': 'violation', 'not_applicable': 'not applicable'}[outcome]
    elif outcome == 'inconclusive':
        outcome = None
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError('Unsupported source outcome: ' + str(outcome))
    phrases = case.get('unresolved_judgment_calls')
    if phrases is not None and (not isinstance(phrases, list) or
            any(not isinstance(p, str) or not p.strip() for p in phrases)):
        raise ValueError('Unresolved legal phrases must be explicit nonempty strings')
    definition_hash = source_hashes.get('definition_sha256')
    references = [{'phrase': phrase, 'law_id': case['target_law_id'],
                   'definition_sha256': definition_hash}
                  for phrase in sorted(set(phrases or []))]
    legal = {'classification': 'unresolved' if references else
             'not_unresolved' if phrases == [] else 'unresolved_source',
             'references': references}
    independent = _independent_violation(record, references, outcome)
    if references:
        if outcome not in (None, 'judgment call') and not independent:
            raise ValueError('Resolved outcome conflicts with unresolved legal phrases')
        if not independent:
            outcome = 'judgment call'
    elif outcome == 'judgment call':
        raise ValueError('Judgment call requires source-bound unresolved legal wording')
    if record.get('missing_evidence'):
        reasons.add('missing_observations')
    target_type = case.get('target_type')
    if not isinstance(target_type, str) or not target_type:
        reasons.add('unresolved_source')
        sweep = None
    else:
        sweep = target_type == 'judgment_sweep'
    if outcome is None and not reasons:
        reasons.add('unresolved_source')
    record.update(format=AUTHORITATIVE_FORMAT, expected_label=outcome,
        recording_identity=deepcopy(recording_identity), source_hashes=dict(source_hashes),
        processing_reasons=sorted(reasons), legal_judgment=legal,
        judgment_sweep=sweep,
        sweep_membership={'is_member': sweep, 'sweep_id': case.get('sweep_id'),
                          'source': 'frozen_case.target_type',
                          'definition_sha256': definition_hash},
        classification_method={'id': 'source_bound_outcome', 'version': 2},
        evaluation_status='legal_judgment' if outcome == 'judgment call' else
                          'checked' if outcome is not None else 'blocked',
        evidence_status='needs_repair' if 'missing_observations' in reasons or
                        record.get('evidence_status') == 'needs_repair' else 'accepted')
    record.setdefault('evaluation_method', 'source_bound_retained_evidence')
    record['reference_check'] = assessment_reference(record.get('reference_check'))
    record.setdefault('evidence', {})
    record['source_signature'] = source_signature(record)
    return validate_authoritative(record)


def validate_authoritative(record):
    """Reject stale or contradictory final outcome records before presentation."""
    if record.get('format') != AUTHORITATIVE_FORMAT:
        raise ValueError('Expected authoritative production-verdict-v2 record')
    if not record.get('case_id') or not record.get('target_law_id') or not record.get('recording_identity'):
        raise ValueError('Authoritative label requires case, law and recording identity')
    hashes = record.get('source_hashes', {})
    method = record.get('classification_method', {})
    candidates = list(hashes.values())
    if not {'definition_sha256', 'trace_sha256'} <= set(hashes) or any(
            not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v)
            for v in candidates):
        raise ValueError('Authoritative label requires source SHA256 hashes')
    for key in ('definition_sha256', 'trace_sha256'):
        if key in record and record[key] != hashes[key]:
            raise ValueError('Label source hash disagrees with authoritative source signature: '+key)
    if method.get('id') != 'source_bound_outcome' or method.get('version') != 2:
        raise ValueError('Unsupported outcome classification method')
    outcome = record.get('expected_label')
    reasons = record.get('processing_reasons')
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError('Invalid authoritative outcome')
    if not isinstance(reasons, list) or reasons != sorted(set(reasons)) or set(reasons) - PROCESSING_REASONS:
        raise ValueError('Invalid separate processing reasons')
    if outcome is None and not reasons:
        raise ValueError('Unavailable outcome requires a separate processing reason')
    legal = record.get('legal_judgment', {})
    references = legal.get('references', [])
    if legal.get('classification') not in ('unresolved', 'not_unresolved', 'unresolved_source'):
        raise ValueError('Invalid legal judgment classification')
    if bool(references) != (legal.get('classification') == 'unresolved'):
        raise ValueError('Legal judgment classification disagrees with references')
    for ref in references:
        if not ref.get('phrase') or ref.get('law_id') != record['target_law_id'] or ref.get('definition_sha256') != hashes['definition_sha256']:
            raise ValueError('Legal judgment reference is not bound to the frozen definition')
    independent = _independent_violation(record, references, outcome)
    if ((outcome == 'judgment call') != (legal.get('classification') == 'unresolved')
            and not independent):
        raise ValueError('Judgment-call outcome disagrees with source legal classification')
    if outcome in OUTCOMES[:3] and set(reasons) & {'uncertain_applicability','unsupported_evaluation','unresolved_source'}:
        raise ValueError('Resolved outcome conflicts with unavailable applicability or evaluation')
    if outcome in OUTCOMES[:3] and not record.get('reference_check'):
        raise ValueError('Resolved outcome requires a validated reference method')
    sweep = record.get('sweep_membership', {})
    if sweep.get('is_member') is not None and type(sweep['is_member']) is not bool:
        raise ValueError('Sweep membership must be boolean or explicitly unresolved')
    if sweep.get('is_member') != record.get('judgment_sweep') or sweep.get('definition_sha256') != hashes['definition_sha256']:
        raise ValueError('Sweep membership disagrees with frozen source')
    status = 'legal_judgment' if outcome == 'judgment call' else 'checked' if outcome is not None else 'blocked'
    if record.get('evaluation_status') != status or record.get('evidence_status') not in ('accepted', 'needs_repair'):
        raise ValueError('Invalid independent processing status')
    if 'missing_observations' in reasons and record['evidence_status'] != 'needs_repair':
        raise ValueError('Missing observations cannot certify complete evidence')
    if record.get('source_signature') != source_signature(record):
        raise ValueError('Stale authoritative label source signature')
    return record


def presentation(record):
    """The exact shared metadata/README/index classification projection."""
    from copy import deepcopy
    validate_authoritative(record)
    return {key: deepcopy(record[key]) for key in PRESENTATION_FIELDS}


def validate_presentation(record, derived):
    expected = presentation(record)
    if any(derived.get(key) != val for key, val in expected.items()):
        raise ValueError('Derived outcome metadata is stale or contradictory')
    return expected


def finalize_expectation(case, measured, attempt, *, definition_path=None, evaluation_method):
    """Bind each reference evaluator to the same authoritative outcome record."""
    attempt = Path(attempt)
    definition_hash = canonical_hash(case)
    if definition_path is not None:
        definition_path = Path(definition_path)
        if json.loads(definition_path.read_text()) != case:
            raise ValueError('Frozen definition file differs from evaluated case')
        definition_hash = file_hash(definition_path)
    measured['definition_sha256'] = definition_hash
    measured['evaluation_method'] = evaluation_method
    profile_path=attempt/'traffic_spec/adapter_report.json'
    profile=json.loads(profile_path.read_text()) if profile_path.is_file() else {}
    profile_hash=file_hash(profile_path) if profile_path.is_file() else None
    from traffic_spec_adapter.atom_contract import common_profile_complete
    complete=common_profile_complete(profile)
    measured.setdefault('evidence',{})['common_capture_profile']={
        'required_measurements_complete':complete,'report_sha256':profile_hash,
        'required_field_gaps':profile.get('required_field_gaps',{}),
        'processing_limits':profile.get('processing_limits',{})}
    if not complete:
        measured['evidence_status']='needs_repair'
        message='Required common observation profile is incomplete or has no completeness receipt'
        if message not in measured.setdefault('missing_evidence',[]):measured['missing_evidence'].append(message)
    source_hashes={'definition_sha256':definition_hash,'trace_sha256':measured['trace_sha256'],
                   'original_capture_sha256':file_hash(attempt/'trace.jsonl')}
    if profile_hash is not None:source_hashes['adapter_report_sha256']=profile_hash
    return authoritative_record(case, measured,
        recording_identity={'original_capture_sha256': file_hash(attempt/'trace.jsonl'),
                            'attempt': str(attempt.resolve())},
        source_hashes=source_hashes)


def expectation(case, attempt, review, context, *, definition_path=None):
    """Fresh production reference evaluator using the shared v2 authority."""
    measured = _measured_expectation(case, attempt, review, context)
    return finalize_expectation(case, measured, attempt, definition_path=definition_path,
                                evaluation_method='production_reference')
