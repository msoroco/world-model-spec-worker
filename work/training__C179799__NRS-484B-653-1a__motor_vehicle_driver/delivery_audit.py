"""Independent original-source person-interaction delivery audit.

CPU selftests exercise source rejection. A passing original audit still requires
local review of physical motion, camera pixels, access status and worker role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

PREFIX = 'training__C179799__NRS-484B-653-1a__motor_vehicle_driver__selected_ce719cfa__'
CASES = {PREFIX+'condition_a', PREFIX+'condition_b'}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, attempt, saved, output):
    require(case in CASES, 'Select exact person-interaction delivery case')
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance, seal = read(attempt/'acquisition-provenance.json'), read(attempt/'capture-seal.json')
    require(provenance.get('provenance_kind') == 'original_native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(view) == 0 for view in VIEWS),
            'Original Native capture closure incomplete')
    for name, checksum in seal.get('sources', {}).items():
        require(sha(attempt/name) == checksum, 'Sealed original source changed: '+name)
    exit_record, owner = read(attempt/'native-exit.json'), read(attempt/'owner-release.json')
    require(exit_record.get('capture_seal_sha256') == sha(attempt/'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt/'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    config = read(attempt/'config.json')
    packet = read(attempt/'original-context-packet.json')
    context = read(attempt/'native-road-readback.json')
    pixel = read(attempt/'person-pixel-review.json')
    require(config.get('case_id') == packet.get('case_id') == pixel.get('case_id') == case,
            'Exact original encounter identity differs')
    require(packet.get('source_kind') == 'original_native_context' and
            pixel.get('source_kind') == 'independent_original_review' and
            context.get('source_kind') == 'original_native_map_readback',
            'Original context or independent pixel review missing')
    for key in ('highway_or_public_access_source', 'driver_identity_source',
                'vehicle_class_source', 'worker_identity_source', 'worker_role_source',
                'worker_route_relation_source', 'sight_line_source',
                'surface_condition_source', 'nearby_property_source'):
        ref = packet.get(key)
        require(isinstance(ref, dict) and ref.get('path') and
                ref.get('sha256') == sha(attempt/ref['path']),
                'Original cited encounter source changed: '+key)
    if packet.get('access_kind') == 'public_access_premises':
        ref = packet.get('excluded_driveway_and_farm_way_review_source')
        require(isinstance(ref, dict) and ref.get('sha256') == sha(attempt/ref['path']),
                'Original public-access premises exclusion source missing')
    require(pixel.get('actor_trace_sha256') == sha(attempt/'native-person-interaction.jsonl') and
            pixel.get('frame_map_sha256') == sha(attempt/'video_frames.jsonl'),
            'Independent person pixel review changed original trace')
    for view in VIEWS:
        require(pixel.get('camera_sha256', {}).get(view) == sha(attempt/(view+'.mkv')),
                'Independent person pixel camera hash changed: '+view)
    actors, mapping = rows(attempt/'native-person-interaction.jsonl'), rows(attempt/'video_frames.jsonl')
    observations = pixel.get('person_observations', [])
    require(len(actors) == len(mapping) == len(observations) == 600,
            'Complete original 600-frame person and pixel join required')
    for index, (actor, frame, observation) in enumerate(zip(actors, mapping, observations)):
        require(actor.get('frame') == frame.get('video_frame') == observation.get('video_frame') == index and
                actor.get('native_frame') == frame.get('native_frame') and
                actor.get('ego_actor_id') != actor.get('person_actor_id') and
                str(actor.get('ego_blueprint_id', '')).startswith('vehicle.') and
                str(actor.get('person_blueprint_id', '')).startswith('walker.pedestrian.') and
                abs(actor['time_s']-frame['time_s']) < 1e-5 and
                set(frame.get('camera_native_frames', {})) == set(VIEWS) and
                all(frame['camera_native_frames'][view] == frame['native_frame'] for view in VIEWS),
                'Original participant/frame/time join differs')
        require(observation.get('person_camera') in VIEWS and
                observation.get('person_pixel_box_xyxy') and
                observation.get('vehicle_camera') in VIEWS and
                observation.get('vehicle_pixel_box_xyxy'),
                'Original roadside worker and vehicle pixels unreviewed')
    processing = read(saved/'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original processing incomplete')
    result = read(Path(processing['result']).resolve())
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is not True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
            'Original physical encounter remains unverified')
    from worker_exchange.media import audit as decode
    decode_dir = output.parent/(case+'-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt/(view+'.mkv'), 600,
                             receipt=decode_dir/(view+'.json'),
                             mapping_sha256=sha(attempt/'video_frames.jsonl'))
                for view in VIEWS}
    core = Path(processing['version'])/'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes', [])) == 600,
            'Saved original Core scene sequence unavailable')
    audit_receipt = {
        'format': 'worker-delivery-audit', 'passed': True,
        'case_id': case, 'frames': 600,
        'checks': {name: True for name in CHECKS},
        'source_result_sha256': processing['result_sha256'],
        'video': 'overview.mkv', 'video_sha256': sha(attempt/'overview.mkv'),
        'trace': str(core), 'trace_sha256': sha(core),
        'source_decode_receipt_path': str(decode_dir/'overview.json'),
        'source_decode_receipt_sha256': sha(decode_dir/'overview.json'),
        'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
        'auditor_path': str(Path(__file__).resolve()),
        'auditor_sha256': sha(__file__),
        'physical_or_legal_acceptance_claimed_by_worker': False}
    output.write_text(json.dumps(audit_receipt, indent=2, allow_nan=False)+'\n')
    return audit_receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            'Exact original person audit inventory differs')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Diagnostic scratch outside .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt, saved = Path(temp)/'attempt', Path(temp)/'saved'
        attempt.mkdir(); saved.mkdir()
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})+'\n')
        (attempt/'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True})+'\n')
        try:
            audit(case, attempt, saved, Path(temp)/'audit.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic diagnostic rejected for wrong reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic fixture passed original delivery audit')
    print('PASS: six original-source checks inventoried and synthetic delivery rejected')


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
