"""Independent original-source audit for exact bus standing delivery cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'analysis'))
from bus_standing import CAMERAS, measure_saved

AID = 'training__C386410__LVMC-11-60-030-A1__bus_driver'
CASES = {AID + '__' + suffix for suffix in (
    'designated_terminus', 'undesignated_street', 'bus_stop', 'bus_stand',
    'route_origin', 'transient_stop', 'parking_other_street', 'tour_bus_other_street')}
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


def audit(case, attempt, saved, output):
    require(case in CASES, 'Select exact bus standing delivery case')
    attempt, saved, output = map(lambda p: Path(p).resolve(), (attempt, saved, output))
    provenance = read(attempt / 'acquisition-provenance.json')
    seal = read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') == 'native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(name) == 0 for name in CAMERAS),
            'Original Native capture closure incomplete')
    for name, checksum in seal.get('sources', {}).items():
        require(sha(attempt / name) == checksum, 'Sealed original source changed: ' + name)
    config = read(attempt / 'config.json')
    require(config.get('case_id') == case, 'Original case identity differs')
    exit_record, owner = read(attempt / 'native-exit.json'), read(attempt / 'owner-release.json')
    require(exit_record.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt / 'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    processing = read(saved / 'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False and
            processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original processing incomplete')
    result = read(Path(processing['result']).resolve())
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is not True and
            result.get('maneuver_completed') is True,
            'Saved original bus physical completion unverified')
    measured = measure_saved(attempt)
    require(measured['stationary_frames'] > 0 and measured['zone_occupied_frames'] > 0,
            'Original stationary bus event or zone occupancy absent')
    review = read(attempt / 'bus-original-review.json')
    require(review.get('case_id') == case and review.get('reviewer') and
            all(review.get(key) is True for key in
                ('vehicle_class_reviewed', 'route_assignment_reviewed',
                 'street_status_reviewed', 'standing_or_parking_reviewed',
                 'all_participants_reviewed', 'actual_pixels_reviewed')),
            'Independent original bus identity, place or activity review missing')
    required = ('road.xodr', 'bus-context.json', 'bus-history.jsonl',
                'video_frames.jsonl', *(name + '.mkv' for name in CAMERAS))
    require(review.get('source_sha256') == {name: sha(attempt / name) for name in required},
            'Independent review does not bind exact original sources')
    context = read(attempt / 'bus-context.json')
    if context['zone']['kind'] != 'other_street':
        authority = review.get('designation_authority_source', {})
        source = Path(authority.get('path', ''))
        require(source.is_file() and authority.get('sha256') == sha(source) and
                review.get('designation_extract', {}).get('route_id') == context['route_id'] and
                review.get('designation_extract', {}).get('zone_id') == context['zone']['id'],
                'Official route endpoint designation source missing or unbound')
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    require(repo is not None, 'Worker runtime unavailable')
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(output.parent)
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {name: decode(attempt / (name + '.mkv'), 600,
                 receipt=decode_dir / (name + '.json'),
                 mapping_sha256=sha(attempt / 'video_frames.jsonl')) for name in CAMERAS}
    core = Path(processing['version']) / 'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes', [])) == 600,
            'Saved original Core scene sequence unavailable')
    receipt = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case,
               'frames': 600, 'checks': {name: True for name in CHECKS},
               'source_result_sha256': processing['result_sha256'],
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': str(core), 'trace_sha256': sha(core),
               'source_decode_receipt_path': str(decode_dir / 'front.json'),
               'source_decode_receipt_sha256': sha(decode_dir / 'front.json'),
               'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
               'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': sha(__file__),
               'source_measurement': measured, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def selftest(case, negative):
    require(case in CASES and len(CHECKS) == 6, 'Audit inventory differs')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Diagnostic scratch outside .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        attempt = Path(directory) / 'attempt'
        saved = Path(directory) / 'saved'
        attempt.mkdir(); saved.mkdir()
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        (attempt / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True}) + '\n')
        try:
            audit(case, attempt, saved, Path(directory) / 'audit.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic fixture rejected for wrong reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic fixture passed original delivery')
    print('PASS six delivery checks inventoried; synthetic original rejected')


def main():
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


if __name__ == '__main__':
    main()
