"""Independent original-source bus terminus delivery audit.

CPU selftests inventory required checks and reject synthetic acquisition. Original
delivery additionally needs a separately source-bound authority/activity review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from measure import measure

AID = 'training__C393261__LVMC-11-60-030-A5__bus_driver'
CASES = {AID + '__probe_01', AID + '__probe_02'}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def inspect_sources(case, attempt):
    config = read(attempt / 'config.json')
    require(config.get('case_id') == case, 'Exact original bus case differs')
    review = read(attempt / 'terminus-review.json')
    require(review.get('review_kind') == 'original_native_source' and
            review.get('case_id') == case, 'Original Native terminus review missing')
    for name, checksum in review.get('source_sha256', {}).items():
        require(sha(attempt / name) == checksum, 'Reviewed bus source changed: ' + name)
    history = rows(attempt / 'terminus-history.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    require(len(history) == len(mapping) == 600,
            'Original 600-frame bus source join incomplete')
    for i, (pose, frame) in enumerate(zip(history, mapping)):
        require(pose.get('video_frame') == frame.get('video_frame') == i and
                pose.get('native_frame') == frame.get('native_frame') and
                abs(pose.get('time_s', -10) - frame.get('time_s', -20)) < .005 and
                set(frame.get('camera_native_frames', {})) == set(VIEWS) and
                all(frame['camera_native_frames'][view] == pose['native_frame']
                    for view in VIEWS), 'Original bus frame/camera join differs')
    measured = measure(attempt / 'terminus-history.jsonl',
                       attempt / 'terminus-context.json')
    require(measured['longest_complete_interval_s'] > 0,
            'No complete original stopped bus dwell')
    return measured


def audit(case, attempt, saved, output):
    require(case in CASES, 'Select exact bus terminus delivery case')
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance = read(attempt / 'acquisition-provenance.json')
    seal = read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') in ('native', 'original_native') and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and
            seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed',
                                   'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(view) == 0 for view in VIEWS),
            'Original Native capture closure incomplete')
    for name, digest in seal.get('sources', {}).items():
        require(sha(attempt / name) == digest, 'Sealed original source changed: ' + name)
    exit_record, owner = read(attempt / 'native-exit.json'), read(attempt / 'owner-release.json')
    require(exit_record.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt / 'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    processing = read(saved / 'processing.json')
    require(processing.get('case_id') == case and
            processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False and
            processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original bus processing incomplete')
    result = read(Path(processing['result']).resolve())
    require(result.get('case_id') == case and
            result.get('provenance_kind') in ('native', 'original_native') and
            result.get('diagnostic_fixture') is not True,
            'Saved original bus result provenance differs')
    measured = inspect_sources(case, attempt)
    independent = read(attempt / 'bus-original-review.json')
    require(all(independent.get(name) is True for name in
                ('non_tour_bus_classification_reviewed',
                 'endpoint_designation_reviewed', 'period_applicability_reviewed',
                 'bus_standing_or_parking_reviewed', 'full_dwell_reviewed',
                 'actual_pixels_reviewed')) and
            independent.get('source_sha256') == {
                name: sha(attempt / name) for name in
                ('road.xodr', 'terminus-context.json', 'terminus-history.jsonl',
                 'video_frames.jsonl', *(view + '.mkv' for view in VIEWS))},
            'Independent original bus designation/activity review missing')
    authority = independent.get('designation_authority_source', {})
    authority_path = Path(authority.get('path', '')).resolve()
    require(authority_path.is_file() and
            authority.get('sha256') == sha(authority_path),
            'Official source-verified designated period missing')
    designation = independent.get('authority_extract', {})
    context = read(attempt / 'terminus-context.json')
    require(designation.get('endpoint_id') == context.get('endpoint_id') and
            type(designation.get('period_s')) in (int, float) and
            designation['period_s'] > 0 and
            independent.get('designated_period_s') == designation['period_s'],
            'Official designated period does not bind original endpoint')
    repo = next((p for p in Path(__file__).resolve().parents
                 if (p / 'batch.json').is_file()), None)
    require(repo is not None, 'Worker runtime unavailable')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt / (view + '.mkv'), 600,
                             receipt=decode_dir / (view + '.json'),
                             mapping_sha256=sha(attempt / 'video_frames.jsonl'))
                for view in VIEWS}
    core = Path(processing['version']) / 'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes', [])) == 600,
            'Saved original bus Core scene sequence unavailable')
    receipt = {'format': 'worker-delivery-audit', 'passed': True,
               'case_id': case, 'frames': 600,
               'checks': {name: True for name in CHECKS},
               'source_result_sha256': processing['result_sha256'],
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': str(core), 'trace_sha256': sha(core),
               'source_decode_receipt_path': str(decode_dir / 'overview.json'),
               'source_decode_receipt_sha256': sha(decode_dir / 'overview.json'),
               'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(__file__),
               'original_designated_period_s': designation['period_s'],
               'original_measured_complete_dwell_s': measured['longest_complete_interval_s'],
               'legal_verdict_claimed': False}
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            'Independent bus audit inventory differs')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Diagnostic scratch outside .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt, saved = Path(temp) / 'attempt', Path(temp) / 'saved'
        attempt.mkdir(); saved.mkdir()
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        (attempt / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True}) + '\n')
        try:
            audit(case, attempt, saved, Path(temp) / 'audit.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic fixture rejected for wrong reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic fixture passed original bus delivery')
    print('PASS six original bus checks inventoried; synthetic delivery rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-fixture', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--saved')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case, args.negative_fixture)
    else:
        print(json.dumps(audit(args.case, args.attempt, args.saved, args.output), sort_keys=True))
