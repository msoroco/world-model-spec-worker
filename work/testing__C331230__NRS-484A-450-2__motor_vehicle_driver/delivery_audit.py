"""Independent audit of original C331230 delivery sources.

Diagnostic mode exercises source and media checks on synthetic fixtures. It never
accepts physical completion, original pixel visibility, or legal sufficiency.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video  # noqa: E402
from worker_exchange.measurement_contract import verify_report  # noqa: E402

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
SOURCES = {'approach_context.json', 'stop_history.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', *(x + '.mkv' for x in CAMERAS)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_native_closure(attempt, expected_frames):
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('frames') != expected_frames or
            seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True or
            seal.get('physical_acceptance_claimed') is not False):
        raise ValueError('Native capture closure absent or inconsistent')
    sources = seal.get('sources')
    if not isinstance(sources, dict) or not SOURCES <= set(sources):
        raise ValueError('Native capture seal omits original source')
    for name, expected in sources.items():
        source = (attempt / name).resolve()
        if attempt not in source.parents or not source.is_file() or digest(source) != expected:
            raise ValueError('Sealed Native original missing or stale: ' + name)
    revision = seal.get('native_revision')
    if (not isinstance(revision, dict) or
            revision.get('construction_sha256') != digest(attempt / 'construction.json') or
            revision.get('runner_sha256') != digest(attempt / 'runner.py')):
        raise ValueError('Native construction revision differs')
    native_exit = read(attempt / 'native-exit.json')
    if (native_exit.get('event') != 'native_exit' or
            native_exit.get('native_revision') != revision or
            native_exit.get('capture_seal_sha256') != digest(attempt / 'capture-seal.json')):
        raise ValueError('Native exit does not bind sealed capture')
    owner = read(attempt / 'owner-release.json')
    if (owner.get('event') != 'owner_released' or owner.get('operator_attested') is not True or
            owner.get('native_construction_sha256') != digest(attempt / 'construction.json') or
            owner.get('native_exit_sha256') != digest(attempt / 'native-exit.json')):
        raise ValueError('Owner release does not bind Native exit')
    return {'capture_seal_sha256': digest(attempt / 'capture-seal.json'),
            'native_exit_sha256': digest(attempt / 'native-exit.json'),
            'owner_release_sha256': digest(attempt / 'owner-release.json')}


def verify_pixels(attempt, review, frames, mapping_hash):
    observations = review.get('observations')
    if not isinstance(observations, list) or not observations:
        raise ValueError('Independent original pixel observations missing')
    if {row.get('camera') for row in observations} != set(CAMERAS):
        raise ValueError('Independent original pixel review omits camera')
    for camera, dimensions in CAMERAS.items():
        samples = [row for row in observations if row.get('camera') == camera]
        pending = {}
        for sample in samples:
            index, box = sample.get('video_frame'), sample.get('bbox_xyxy')
            if (type(index) is not int or not 0 <= index < frames or
                    not isinstance(box, list) or len(box) != 4 or
                    any(type(value) is not int for value in box)):
                raise ValueError('Independent original pixel sample invalid')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= dimensions[0] and 0 <= y0 < y1 <= dimensions[1]
                    and (x1 - x0) * (y1 - y0) >= 16):
                raise ValueError('Independent original pixel box invalid')
            pending.setdefault(index, []).append(box)
        seen = set()

        def check(frame):
            if (frame.width, frame.height) != dimensions:
                raise ValueError('Reviewed camera dimensions differ')
            for box in pending.get(frame.index, []):
                x0, y0, x1, y1 = box
                colors = set()
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        offset = 3 * (y * frame.width + x)
                        colors.add(frame.pixels[offset:offset + 3])
                        if len(colors) > 1:
                            break
                    if len(colors) > 1:
                        break
                if len(colors) < 2:
                    raise ValueError('Reviewed original pixel ROI has no detail')
                seen.add((frame.index, tuple(box)))

        audit_video(attempt / (camera + '.mkv'), frames,
                    checkers={'reviewed_original_pixels': (digest(__file__), check)},
                    mapping_sha256=mapping_hash)
        if seen != {(row['video_frame'], tuple(row['bbox_xyxy'])) for row in samples}:
            raise ValueError('Reviewed original pixel frame not decoded')


def audit(case_id, attempt, diagnostic=False, pixel_review=None):
    attempt = Path(attempt).resolve()
    manifest = read(PACKAGE / 'execution-manifest.json')
    entries = [x for x in manifest['cases'] if x['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unknown exact C331230 case')
    entry = entries[0]
    config, result = read(attempt / 'config.json'), read(attempt / 'result.json')
    if config.get('selected_case_id') != case_id or result.get('case_id') != case_id:
        raise ValueError('Exact case identity differs')
    if tuple(config.get(x) for x in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s')) != (
            'NRS-484A-450-2', 'C331230', 'motor_vehicle_driver', 20, 45):
        raise ValueError('Exact law, cell, actor or capture profile differs')
    provenance = 'synthetic_fixture' if diagnostic else 'native'
    if (result.get('provenance_kind') != provenance or
            result.get('diagnostic_fixture') is not diagnostic or
            result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Original provenance or physical acceptance claim differs')
    hashes = result.get('source_evidence_hashes')
    if not isinstance(hashes, dict) or not SOURCES <= set(hashes):
        raise ValueError('Required original source hash absent')
    for name, expected in hashes.items():
        source = (attempt / name).resolve()
        if attempt not in source.parents or not source.is_file() or digest(source) != expected:
            raise ValueError('Missing or changed original source: ' + name)
    if result.get('capture_evidence_sha256') != digest(attempt / 'capture/evidence.jsonl'):
        raise ValueError('Capture evidence hash differs')
    if result.get('video_frame_map_reference') != 'video_frames.jsonl' or result.get('trace_reference') != 'trace.jsonl':
        raise ValueError('Original frame/trace reference differs')
    if set(result.get('video_references', [])) != {x + '.mkv' for x in CAMERAS}:
        raise ValueError('All four original cameras required')
    mapping = rows(attempt / 'video_frames.jsonl')
    frames = len(mapping)
    if frames < 2 or (not diagnostic and frames != 900):
        raise ValueError('Full planned 900-frame capture duration missing')
    previous_frame, previous_time = -1, -math.inf
    for i, row in enumerate(mapping):
        frame, time = row.get('carla_frame'), row.get('time_s')
        if (row.get('video_frame') != i or type(frame) is not int or frame <= previous_frame or
                type(time) not in (int, float) or not math.isfinite(time) or time <= previous_time):
            raise ValueError('Original frame/time mapping differs')
        if i and abs(time - previous_time - .05) > .001:
            raise ValueError('Original frame rate differs')
        previous_frame, previous_time = frame, time
    original_histories = {}
    for name in ('stop_history.jsonl', 'trace.jsonl'):
        original = rows(attempt / name)
        if len(original) != frames or any(row.get('frame') != mapping[i]['carla_frame'] or
                row.get('time_s') != mapping[i]['time_s'] for i, row in enumerate(original)):
            raise ValueError('Original participant/time join differs: ' + name)
        original_histories[name] = original
    capture = rows(attempt / 'capture/evidence.jsonl')
    if len(capture) != frames:
        raise ValueError('Original capture frame/time join differs')
    for i, row in enumerate(capture):
        mapped = mapping[i]
        if (row.get('original_frame') != mapped['carla_frame'] or
                row.get('recording_time_s') != mapped['time_s']):
            raise ValueError('Original capture frame/time join differs')
        observations = row.get('original_observations')
        if observations is None:
            if not diagnostic:
                raise ValueError('Original participant inventory missing')
            continue
        if (not isinstance(observations, dict) or
                observations.get('frame') != mapped['carla_frame'] or
                observations.get('time_s') != mapped['time_s']):
            raise ValueError('Original observation frame/time join differs')
        participants = observations.get('participants')
        actor_id = row.get('actor_id')
        if (not isinstance(participants, list) or not participants or
                type(actor_id) is not int or
                len({participant.get('actor_id') for participant in participants}) != len(participants) or
                actor_id not in {participant.get('actor_id') for participant in participants}):
            raise ValueError('Original participant inventory missing or inconsistent')
        ego = next(participant for participant in participants if participant['actor_id'] == actor_id)
        measured_speed = original_histories['stop_history.jsonl'][i].get('ego_speed_mps')
        if (ego.get('speed_mps') != measured_speed or
                row.get('ego', {}).get('speed_mps') != measured_speed):
            raise ValueError('Original ego speed/capture join differs')
    if case_id.endswith('__no_crosswalk_no_line_first_view'):
        if hashes.get('sight_history.jsonl') != digest(attempt / 'sight_history.jsonl'):
            raise ValueError('Original sight source hash missing or stale')
        sight = rows(attempt / 'sight_history.jsonl')
        if len(sight) != frames:
            raise ValueError('Original sight frame/time join differs')
        for i, row in enumerate(sight):
            mapped = mapping[i]
            approaching, visible = row.get('approaching_traffic_ids'), row.get('visible_approaching_traffic_ids')
            if (row.get('frame') != mapped['carla_frame'] or row.get('time_s') != mapped['time_s'] or
                    not isinstance(approaching, list) or not isinstance(visible, list) or
                    not set(visible) <= set(approaching)):
                raise ValueError('Original sight frame/time or visible-participant join differs')
            observations = capture[i].get('original_observations')
            if observations is not None and not set(approaching) <= {
                    participant.get('actor_id') for participant in observations['participants']}:
                raise ValueError('Original sight participant missing from capture')
    scenes = read(attempt / 'converted/trace.json').get('scenes')
    if not isinstance(scenes, list) or len(scenes) != frames or any(
            scene.get('t') != round(frame['time_s'] * 1000)
            for scene, frame in zip(scenes, mapping)):
        raise ValueError('Converted Core trace/original frame time join differs')
    report = read(attempt / 'analysis-report.json')
    if report.get('case_id') != case_id or report.get('physical_acceptance_claimed') is not False:
        raise ValueError('Saved analysis identity or acceptance claim differs')
    measurements = verify_report(read(PACKAGE / entry['measurement_contract']), report, attempt)
    decodes = {}
    for camera, dimensions in CAMERAS.items():
        source = attempt / (camera + '.mkv')
        decoded = audit_video(source, frames, mapping_sha256=digest(attempt / 'video_frames.jsonl'))
        if tuple(decoded['dimensions']) != dimensions:
            raise ValueError('Original camera dimensions differ: ' + camera)
        decodes[camera] = {'source_sha256': digest(source), 'frames': decoded['frames'],
                           'rgb_sequence_sha256': decoded['rgb_sequence_sha256']}
    composed = audit_video(attempt / 'raw.mkv', frames,
                           mapping_sha256=digest(attempt / 'video_frames.jsonl'))
    composition = read(attempt / 'four-view-receipt.json')
    if (composition.get('format') != 'synchronized-four-view' or
            composition.get('sources') != {name: digest(attempt / (name + '.mkv')) for name in CAMERAS} or
            composition.get('frame_map_sha256') != digest(attempt / 'video_frames.jsonl') or
            composition.get('primary_sha256') != composed['video_sha256'] or
            composition.get('frames') != frames or
            composition.get('dimensions') != composed['dimensions']):
        raise ValueError('Four-view composition receipt missing or stale')
    if diagnostic:
        return {'format': 'worker-c331230-independent-delivery-audit', 'case_id': case_id,
                'diagnostic_only': True, 'software_checks_passed': True,
                'physical_completion_verified': False, 'actual_pixels_verified': False,
                'physical_acceptance_claimed': False, 'frames': frames,
                'measurement_names': sorted(measurements), 'camera_decodes': decodes,
                'composed_video_sha256': composed['video_sha256']}
    closure = verify_native_closure(attempt, frames)
    # Native acceptance requires a separate human review of the original pixels.
    review = read(pixel_review) if pixel_review else None
    if not review or review.get('case_id') != case_id or not review.get('reviewer') or not review.get('method'):
        raise ValueError('Independent original pixel review missing')
    if (review.get('frame_map_sha256') != digest(attempt / 'video_frames.jsonl') or
            review.get('source_sha256') != {x: digest(attempt / (x + '.mkv')) for x in CAMERAS} or
            set(review.get('reviewed_cameras', [])) != set(CAMERAS)):
        raise ValueError('Independent original pixel review missing or stale')
    verify_pixels(attempt, review, frames, digest(attempt / 'video_frames.jsonl'))
    if result.get('maneuver_completed') is not True or any(
            result.get('physical_checks', {}).get(x, {}).get('status') != 'met'
            for x in ('setup', 'target', 'maneuver')):
        raise ValueError('Source-bound physical completion absent')
    for key in ('setup', 'target', 'maneuver'):
        check = result['physical_checks'][key]
        if not check.get('method') or not check.get('intervals') or not check.get('sources'):
            raise ValueError('Source-bound physical completion evidence absent: ' + key)
        for name, expected in check['sources'].items():
            source = (attempt / name).resolve()
            if attempt not in source.parents or not source.is_file() or digest(source) != expected:
                raise ValueError('Physical completion source missing or stale: ' + name)
    return {'format': 'worker-c331230-independent-delivery-audit', 'case_id': case_id,
            'diagnostic_only': False, 'software_checks_passed': True,
            'physical_completion_verified': True, 'actual_pixels_verified': True,
            'physical_acceptance_claimed': False, 'frames': frames,
            'measurement_names': sorted(measurements), 'camera_decodes': decodes,
            'composed_video_sha256': composed['video_sha256'], 'native_closure': closure}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--pixel-review', type=Path)
    parser.add_argument('--all-diagnostics', action='store_true')
    args = parser.parse_args()
    if args.all_diagnostics:
        for entry in read(PACKAGE / 'execution-manifest.json')['cases']:
            case_id = entry['case_id']
            command = entry['post_capture']['command'].split()
            attempt = (REPO / command[command.index('--attempt') + 1]).resolve()
            receipt = audit(case_id, attempt, diagnostic=True)
            if (not receipt['software_checks_passed'] or receipt['physical_acceptance_claimed'] or
                    receipt['actual_pixels_verified'] or receipt['physical_completion_verified']):
                raise AssertionError('Diagnostic acceptance boundary differs')
            with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c331230-audit-') as temporary:
                altered = Path(temporary) / 'attempt'
                shutil.copytree(attempt, altered)
                (altered / 'stop_history.jsonl').unlink()
                try:
                    audit(case_id, altered, diagnostic=True)
                except ValueError as exc:
                    if 'Missing or changed original source: stop_history.jsonl' not in str(exc):
                        raise
                else:
                    raise AssertionError('Removed original source accepted')
                shutil.copy2(attempt / 'stop_history.jsonl', altered / 'stop_history.jsonl')
                trace = read(altered / 'converted/trace.json')
                trace['scenes'][0]['t'] += 1
                (altered / 'converted/trace.json').write_text(json.dumps(trace) + '\n')
                try:
                    audit(case_id, altered, diagnostic=True)
                except ValueError as exc:
                    if 'Converted Core trace/original frame time join differs' not in str(exc):
                        raise
                else:
                    raise AssertionError('Changed converted time join accepted')
                shutil.copy2(attempt / 'converted/trace.json', altered / 'converted/trace.json')
                capture_path = altered / 'capture/evidence.jsonl'
                capture_rows = rows(capture_path)
                capture_rows[0]['recording_time_s'] += .05
                capture_path.write_text(''.join(json.dumps(row) + '\n' for row in capture_rows))
                result = read(altered / 'result.json')
                result['source_evidence_hashes']['capture/evidence.jsonl'] = digest(capture_path)
                result['capture_evidence_sha256'] = digest(capture_path)
                (altered / 'result.json').write_text(json.dumps(result) + '\n')
                try:
                    audit(case_id, altered, diagnostic=True)
                except ValueError as exc:
                    if 'Original capture frame/time join differs' not in str(exc):
                        raise
                else:
                    raise AssertionError('Changed original capture time accepted')
                if case_id.endswith('__no_crosswalk_no_line_first_view'):
                    shutil.copy2(attempt / 'capture/evidence.jsonl', capture_path)
                    sight_path = altered / 'sight_history.jsonl'
                    sight_rows = rows(sight_path)
                    sight_rows[0]['time_s'] += .05
                    sight_path.write_text(''.join(json.dumps(row) + '\n' for row in sight_rows))
                    result['source_evidence_hashes']['capture/evidence.jsonl'] = digest(capture_path)
                    result['capture_evidence_sha256'] = digest(capture_path)
                    result['source_evidence_hashes']['sight_history.jsonl'] = digest(sight_path)
                    (altered / 'result.json').write_text(json.dumps(result) + '\n')
                    try:
                        audit(case_id, altered, diagnostic=True)
                    except ValueError as exc:
                        if 'Original sight frame/time or visible-participant join differs' not in str(exc):
                            raise
                    else:
                        raise AssertionError('Changed original sight time accepted')
            try:
                audit(case_id, attempt, diagnostic=False)
            except ValueError as exc:
                if 'Original provenance' not in str(exc):
                    raise
            else:
                raise AssertionError('Synthetic source accepted as Native')
            print(json.dumps({'case_id': case_id, 'source_and_media': 'passed',
                              'cameras': len(receipt['camera_decodes']),
                              'removed_source': 'rejected', 'changed_core_time': 'rejected',
                              'changed_capture_time': 'rejected',
                              'changed_sight_time': ('rejected' if case_id.endswith('__no_crosswalk_no_line_first_view') else 'not_applicable'),
                              'synthetic_as_native': 'rejected',
                              'physical_acceptance_claimed': False}, sort_keys=True))
    else:
        if not args.case or not args.attempt:
            parser.error('--case and --attempt required without --all-diagnostics')
        print(json.dumps(audit(args.case, args.attempt, args.diagnostic, args.pixel_review), sort_keys=True))
