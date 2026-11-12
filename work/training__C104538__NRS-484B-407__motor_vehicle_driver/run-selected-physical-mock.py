"""Exercise C104538 physical branches on retained diagnostic sources only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physical_motion_audit import audit, check_lifecycle, classify, rows, LIFECYCLE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ('below_500_ft', 'at_500_ft', 'above_500_ft')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_for(suffix):
    name = 'below-primary' if suffix == 'below_500_ft' else suffix + '-primary'
    return ROOT / '.runtime-work' / ('c104538-update023-' + name + '-compat')


def run(suffix, kind):
    manifest = json.loads((HERE/'execution-manifest.json').read_text())
    case = HERE.name + '__' + suffix
    entry = next(x for x in manifest['cases'] if x['case_id'] == case)
    base = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'original_native_motion_verified': False,
            'original_two_direction_pixels_verified': False, 'accepted': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        events = list(LIFECYCLE)
        assert check_lifecycle(events)['saved_processing_after_owner_release']
        bad = events.copy();bad[-2:] = reversed(bad[-2:])
        try: check_lifecycle(bad)
        except ValueError: pass
        else: raise AssertionError('Premature saved processing accepted')
        return {**base, 'events': events, 'exit_code': 0,
                'original_owner_release_verified': False}
    source = source_for(suffix)
    positive = audit(source, case, diagnostic=True)
    assert positive['source_shaped_motion_status'] == 'met'
    assert positive['native_motion_status'] == 'unverified'
    try: audit(source, case, diagnostic=False)
    except ValueError as exc:
        assert 'Synthetic source cannot prove original Native motion' in str(exc)
    else: raise AssertionError('Synthetic reversal accepted as original')
    names = ('native_body_history.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl')
    history, trace, evidence, mapping = [rows(source/name) for name in names]
    for movement, capture in zip(trace, evidence):
        assert movement.get('speed_provenance') == 'synthetic_native_sample'
        assert capture['ego'].get('speed_provenance') == 'synthetic_native_sample'
    if kind == 'incomplete_motion':
        history, evidence = copy.deepcopy(history), copy.deepcopy(evidence)
        for body, capture in zip(history, evidence):
            body['ego_heading_deg'] = -90.0
            capture['ego']['heading_deg'] = -90.0
    elif kind == 'missing_evidence':
        mapping = mapping[:-1]
    try:
        measured = classify(history, trace, evidence, mapping, 480)
        status = measured['status']
    except ValueError:
        if kind != 'missing_evidence': raise
        measured, status = {}, 'unverified'
    expected = {'complete_motion':'met','incomplete_motion':'not_met',
                'missing_evidence':'unverified'}[kind]
    assert status == expected, (suffix, kind, status)
    return {**base, 'physical_checks': {'maneuver': {
        'status': status, 'method': '480-frame source-joined body/trace reversal classifier on diagnostic fixture',
        'sources': list(names)}}, 'maneuver_completed': status == 'met',
        'realized_observables': measured if status == 'met' else {},
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'mock_native_branch_only': True, 'mock_input_provenance': 'synthetic_native_sample',
        'original_production_audit_rejected': True,
        'source_sha256': {name:sha(source/name) for name in names}}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=SUFFIXES,required=True)
    p.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=run(a.case,a.kind);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':result['case_id'],'kind':a.kind,
                      'status':result.get('physical_checks',{}).get('maneuver',{}).get('status'),
                      'cpu_fixture_mock':True,'original_native_motion_verified':False}))
