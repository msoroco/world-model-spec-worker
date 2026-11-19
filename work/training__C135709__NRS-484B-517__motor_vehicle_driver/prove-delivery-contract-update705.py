"""CPU mechanics proof for the independent original stand delivery auditor.

All candidate sources here are synthetic diagnostics. The production entrypoint
must reject them and cannot emit an accepted original recording receipt.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange import media


def load_auditor():
    spec = importlib.util.spec_from_file_location(
        'c135709_delivery_audit', ROOT/'native/delivery_audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prove(case):
    audit = load_auditor()
    designation = {'source_kind': 'external_official_record',
                   'issuer': 'CPU fixture only', 'order_or_citation': 'CPU fixture only',
                   'effective_date': 'CPU fixture only',
                   'stand_location': 'CPU fixture only',
                   'document_reference': 'CPU fixture only'}
    audit.validate_designation_record(designation)
    altered_designation = dict(designation, issuer='')
    try:
        audit.validate_designation_record(altered_designation)
    except ValueError as error:
        assert 'incomplete' in str(error)
    else:
        raise AssertionError('Designation without issuer was accepted')
    source_hashes = {name: ('a' if name == 'designation-record.json' else 'b')*64
                     for name in set(audit.CONTEXT_SOURCES.values())}
    findings = {term: {'observed': False, 'source': source,
                       'source_sha256': source_hashes[source],
                       'review_note': 'CPU schema fixture; no original fact asserted'}
                for term, source in audit.CONTEXT_SOURCES.items()}
    assert len(audit.validate_context_findings(
        {'context_findings': findings}, source_hashes)) == len(findings)
    changed = copy.deepcopy(findings)
    changed['official_designation']['source_sha256'] = '0'*64
    try:
        audit.validate_context_findings({'context_findings': changed}, source_hashes)
    except ValueError as error:
        assert 'lacks source' in str(error)
    else:
        raise AssertionError('Unbound designation finding was accepted')
    changed = copy.deepcopy(findings)
    del changed['taxicab_waiting_or_approaching']
    try:
        audit.validate_context_findings({'context_findings': changed}, source_hashes)
    except ValueError as error:
        assert 'incomplete' in str(error)
    else:
        raise AssertionError('Missing entitled-vehicle review was accepted')
    witness = case.rsplit('__', 1)[-1]
    checked = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        version = (REPO/'.runtime-work/c135709-update703-selected-matrix/f6886b74cf13'/witness/
                   candidate/'saved/v0001')
        analysis = version/'analysis'
        config, result = audit.read(analysis/'config.json'), audit.read(analysis/'result.json')
        assert config['case_id'] == result['case_id'] == case
        assert config['candidate_id'] == candidate
        assert result['provenance_kind'] == 'synthetic_local_diagnostic'
        actors = audit.rows(analysis/'native-raw-actors.jsonl')
        frames = audit.rows(analysis/'video_frames.jsonl')
        trace = audit.rows(analysis/'trace.jsonl')
        reviews = audit.rows(analysis/'stand-review.jsonl')
        joined = audit.validate_rows(actors, frames, trace, reviews,
                                     source_kind='synthetic_cpu')
        assert joined['frames'] == 240
        if candidate == 'primary':
            damaged = copy.deepcopy(actors)
            damaged[0]['ego']['speed_mps'] += 1
            try:
                audit.validate_rows(damaged, frames, trace, reviews,
                                    source_kind='synthetic_cpu')
            except ValueError as error:
                assert 'join differs' in str(error)
            else:
                raise AssertionError('Changed source speed was accepted')
            try:
                audit.validate_rows(actors, frames, trace, reviews[:-1],
                                    source_kind='synthetic_cpu')
            except ValueError as error:
                assert 'count differs' in str(error)
            else:
                raise AssertionError('Missing review frame was accepted')
        media.check_four_view_sources({name: analysis/(name+'.mkv')
                                       for name in audit.CAMERAS})
        if candidate == 'primary':
            try:
                media.check_four_view_sources({name: analysis/(name+'.mkv')
                                               for name in audit.CAMERAS[:-1]})
            except ValueError as error:
                assert 'Four named' in str(error)
            else:
                raise AssertionError('Missing source camera was accepted')
        # Saved processing already decoded every review frame; verify its exact
        # source-bound receipt rather than claiming semantic pixel visibility.
        media.verify_receipt(analysis/'event_review.webm',
                             version/'final-decode.json', 240)
        checked.append(candidate)
    # Exercise the independent pixel checker with a synthetic RGB frame.
    boxes = [{'claim': claim, 'frame': 0, 'rect_xywh': [0, 0, 3, 3]}
             for claim in sorted(audit.CLAIMS)]
    check, seen = audit.pixel_checker(boxes)
    check(media.Frame(0, 3, 3, bytes(range(27))))
    assert seen == audit.CLAIMS
    try:
        check(media.Frame(0, 3, 3, bytes([1]*27)))
    except ValueError as error:
        assert 'flat' in str(error)
    else:
        raise AssertionError('Flat reviewed pixels passed')
    return {'case_id': case, 'candidate_ids': checked,
            'checks_exercised': list(audit.CHECKS),
            'joined_synthetic_frames_per_candidate': 240,
            'full_decode_receipts_verified': 4,
            'pixel_checker_positive_and_flat_negative': True,
            'context_findings_positive_and_missing_source_negatives': True,
            'designation_record_positive_and_missing_issuer_negative': True,
            'changed_speed_missing_review_and_camera_negatives': True,
            'original_native_observed': False, 'accepted_recording': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--reject-synthetic', action='store_true')
    args = parser.parse_args()
    if args.case not in (ROOT.name+'__reference', ROOT.name+'__contrast'):
        raise ValueError('Unknown exact delivery case')
    if args.reject_synthetic:
        witness = args.case.rsplit('__', 1)[-1]
        attempt = (REPO/'.runtime-work/c135709-update703-selected-matrix/f6886b74cf13'/witness/
                   'primary/saved/v0001/analysis')
        audit = load_auditor()
        audit.audit_original(attempt, args.case, attempt/'missing-human-review.json',
                             REPO/'.runtime-work/c135709-update705-rejected'/witness/'receipt.json',
                             REPO/'.runtime-work/c135709-update705-rejected'/witness/'decode.json')
        raise AssertionError('Production accepted synthetic rows as original Native')
    print(json.dumps(prove(args.case), sort_keys=True))


if __name__ == '__main__':
    main()
