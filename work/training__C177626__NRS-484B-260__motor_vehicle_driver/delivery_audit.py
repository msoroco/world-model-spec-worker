"""Independent original-source private-way entry delivery audit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

AID = 'training__C177626__NRS-484B-260__motor_vehicle_driver'
CASES = {AID + '__probe_a', AID + '__probe_b'}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect_original(case, attempt):
    config = read(attempt / 'config.json')
    require(config.get('case_id') == case, 'Exact private-way case differs')
    context = read(attempt / 'private-entry-context.json')
    require(context.get('source_kind') == 'original_native_private_way_entry' and
            context.get('private_way_and_highway') and
            context.get('all_vehicle_inventory_method'),
            'Original private-way/highway context absent')
    review = read(attempt / 'private-entry-review.json')
    require(review.get('case_id') == case, 'Original private-way review case differs')
    for name, digest in review.get('source_sha256', {}).items():
        require(sha(attempt / name) == digest, 'Reviewed original source changed: ' + name)
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    require(repo is not None, 'Worker runtime root absent')
    sys.path.insert(0, str(repo / 'work' / AID / 'native'))
    from finalize import measure_entry
    measured = measure_entry(attempt)
    require(measured['highway_vehicle_count'] >= 2 and
            len(measured['all_approaching_highway_actor_ids']) == measured['highway_vehicle_count'],
            'All approaching highway vehicles not measured')
    return measured


def audit(case, attempt, saved, output):
    require(case in CASES, 'Select exact private-way delivery case')
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance, seal = read(attempt / 'acquisition-provenance.json'), read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') in ('native', 'original_native') and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
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
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False and
            processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original private-way processing incomplete')
    result = read(Path(processing['result']).resolve())
    require(result.get('case_id') == case and result.get('provenance_kind') in
            ('native', 'original_native') and result.get('diagnostic_fixture') is not True,
            'Saved original result provenance differs')
    measured = inspect_original(case, attempt)
    independent = read(attempt / 'private-entry-original-review.json')
    require(all(independent.get(name) is True for name in
                ('private_way_and_highway_reviewed', 'all_approaching_vehicles_reviewed',
                 'continuous_entry_reviewed', 'actual_pixels_reviewed',
                 'physical_completion_reviewed')) and
            independent.get('source_sha256') == {name: sha(attempt / name) for name in
                ('road.xodr', 'private-entry-context.json', 'private-entry-actors.jsonl',
                 'video_frames.jsonl', 'trace.jsonl', *(view + '.mkv' for view in VIEWS))},
            'Independent all-vehicle entry/pixel review missing')
    sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents
                                if (p / 'batch.json').is_file()) / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt / (view + '.mkv'), 600,
                             receipt=decode_dir / (view + '.json'),
                             mapping_sha256=sha(attempt / 'video_frames.jsonl')) for view in VIEWS}
    core = Path(processing['version']) / 'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes', [])) == 600,
            'Saved original Core scene sequence unavailable')
    receipt = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case,
               'frames': 600, 'checks': {name: True for name in CHECKS},
               'source_result_sha256': processing['result_sha256'],
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': str(core), 'trace_sha256': sha(core),
               'source_decode_receipt_path': str(decode_dir / 'overview.json'),
               'source_decode_receipt_sha256': sha(decode_dir / 'overview.json'),
               'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(__file__),
               'original_entry_episode': measured, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(receipt, indent=2).rstrip() + '\n')
    return receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            'Private-way delivery audit inventory differs')
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
            raise AssertionError('Synthetic fixture passed original private-way delivery')
    print('PASS independent six-check inventory; synthetic delivery rejected')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--negative-fixture', action='store_true')
    p.add_argument('--attempt')
    p.add_argument('--saved')
    p.add_argument('--output')
    a = p.parse_args()
    if a.selftest:
        selftest(a.case, a.negative_fixture)
    else:
        print(json.dumps(audit(a.case, a.attempt, a.saved, a.output), sort_keys=True))
