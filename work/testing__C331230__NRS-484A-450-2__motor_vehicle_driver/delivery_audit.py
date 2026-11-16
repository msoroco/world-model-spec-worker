"""Independent audit of original C331230 delivery sources.

Diagnostic mode exercises source and media checks on synthetic fixtures. It never
accepts physical completion, original pixel visibility, or legal sufficiency.
"""
import argparse
import hashlib
import json
import math
import sys
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
    for name in ('stop_history.jsonl', 'trace.jsonl'):
        original = rows(attempt / name)
        if len(original) != frames or any(row.get('frame') != mapping[i]['carla_frame'] or
                row.get('time_s') != mapping[i]['time_s'] for i, row in enumerate(original)):
            raise ValueError('Original participant/time join differs: ' + name)
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
    if diagnostic:
        return {'format': 'worker-c331230-independent-delivery-audit', 'case_id': case_id,
                'diagnostic_only': True, 'software_checks_passed': True,
                'physical_completion_verified': False, 'actual_pixels_verified': False,
                'physical_acceptance_claimed': False, 'frames': frames,
                'measurement_names': sorted(measurements), 'camera_decodes': decodes}
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
            'measurement_names': sorted(measurements), 'camera_decodes': decodes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--pixel-review', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.diagnostic, args.pixel_review), sort_keys=True))
