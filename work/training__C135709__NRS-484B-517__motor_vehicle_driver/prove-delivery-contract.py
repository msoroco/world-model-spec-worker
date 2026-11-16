"""CPU mechanics proof for the independent original stand delivery auditor.

All candidate sources here are synthetic diagnostics. The production entrypoint
must reject them and cannot emit an accepted original recording receipt.
"""
import argparse
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
    witness = case.rsplit('__', 1)[-1]
    checked = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        version = (REPO/'.runtime-work/update052-c135709-saved-all-v2'/witness/
                   candidate/'processed/v0001')
        analysis = version/'analysis'
        config, result = audit.read(analysis/'config.json'), audit.read(analysis/'result.json')
        assert config['case_id'] == result['case_id'] == case
        assert config['candidate_id'] == candidate
        assert result['provenance_kind'] == 'synthetic_local_diagnostic'
        joined = audit.validate_rows(
            audit.rows(analysis/'native-raw-actors.jsonl'),
            audit.rows(analysis/'video_frames.jsonl'),
            audit.rows(analysis/'trace.jsonl'),
            audit.rows(analysis/'stand-review.jsonl'), source_kind='synthetic_cpu')
        assert joined['frames'] == 240
        media.check_four_view_sources({name: analysis/(name+'.mkv')
                                       for name in audit.CAMERAS})
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
        attempt = (REPO/'.runtime-work/update052-c135709-saved-all-v2'/witness/
                   'primary/processed/v0001/analysis')
        audit = load_auditor()
        audit.audit_original(attempt, args.case, attempt/'missing-human-review.json',
                             REPO/'.runtime-work/update053-c135709-rejected'/witness/'receipt.json',
                             REPO/'.runtime-work/update053-c135709-rejected'/witness/'decode.json')
        raise AssertionError('Production accepted synthetic rows as original Native')
    print(json.dumps(prove(args.case), sort_keys=True))


if __name__ == '__main__':
    main()
