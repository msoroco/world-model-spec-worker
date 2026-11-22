"""Independent saved-source delivery audit for four exact speed cases."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from physical_speed_audit import audit_original, classify, read_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
REQUIRED = ('native_samples.jsonl', 'video_frames.jsonl', 'trace.jsonl',
            'body_history.jsonl', 'capture/manifest.json', 'capture/evidence.jsonl',
            'capture/native/frames.jsonl', 'road.xodr',
            *(name + '.mkv' for name in CAMERAS))
REQUESTS = {'below_80_mph': 75.0, 'inside_80_mph': 79.5,
            'at_80_mph': 80.0, 'above_80_mph': 85.0}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, name):
    path = Path(attempt) / name
    require(path.is_file(), 'Missing selected source: ' + name)
    return path


def video_frames(path):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=nb_read_frames',
                          '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         timeout=120)
    require(run.returncode == 0 and run.stdout.strip().isdigit(),
            'Original source video decode failed: ' + path.name)
    return int(run.stdout.strip())


def audit(case_id, candidate_id, attempt, processing_path, *, diagnostic=False):
    manifest_path = HERE / 'current-runtime-reproof-manifest.json'
    manifest = read(manifest_path)
    require(manifest.get('assignment_id') == HERE.name, 'Wrong delivery assignment')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case_id), None)
    require(entry is not None and entry.get('kind') == 'delivery',
            'Unselected speed delivery case')
    suffix = case_id.removeprefix(HERE.name + '__')
    require(suffix in REQUESTS, 'Wrong selected speed case')
    candidate = entry if candidate_id == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate_id), None)
    require(candidate is not None and sha(HERE / candidate['construction']) ==
            candidate['construction_sha256'], 'Selected construction changed')
    attempt = Path(attempt).resolve()
    processing_path = Path(processing_path).resolve()
    require(attempt.is_dir() and processing_path.is_file(),
            'Saved delivery attempt or processing receipt missing')
    selection = read(source(attempt, 'candidate-selection.json'))
    require(selection.get('candidate_id') == candidate_id and
            selection.get('construction_sha256') == candidate['construction_sha256'],
            'Selected candidate source binding differs')
    processing = read(processing_path)
    require(processing.get('passed') is True and processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('passed') is True and
            processing.get('case_id') == case_id and
            processing.get('candidate_id') == candidate_id and
            processing.get('physical_acceptance_claimed') is False and
            processing.get('legal_acceptance_claimed') is False,
            'Saved processing chain incomplete')
    hashes = {}
    for name in REQUIRED:
        path = source(attempt, name)
        hashes[name] = sha(path)
        require(processing.get('original_source_hashes', {}).get(name) == hashes[name],
                'Saved original source changed: ' + name)
    samples = read_rows(source(attempt, 'native_samples.jsonl'))
    mapping = read_rows(source(attempt, 'video_frames.jsonl'))
    physical = classify(samples, mapping, REQUESTS[suffix])
    counts = {name: video_frames(source(attempt, name + '.mkv')) for name in CAMERAS}
    require(set(counts.values()) == {480}, 'Source camera frame count differs')
    result_path = Path(processing.get('result', '')).resolve()
    require(result_path.is_file() and processing_path.parent in result_path.parents,
            'Saved Native result path differs from processing output')
    result = read(result_path)
    require(processing.get('result_sha256') == sha(result_path) and
            result.get('case_id') == case_id and result.get('accepted') is False and
            result.get('legal_verdict_claimed') is False,
            'Sealed Native result differs or claims acceptance')
    synthetic = all(row.get('source_kind') == 'synthetic_cpu_fixture' for row in samples)
    if diagnostic:
        require(synthetic and result.get('provenance_kind') == 'synthetic_local_diagnostic' and
                result.get('maneuver_completed') is False,
                'Synthetic diagnostic source attempted physical promotion')
        return {'format': 'worker-delivery-audit', 'case_id': case_id,
                'candidate_id': candidate_id, 'passed': False,
                'source_shaped_unit_test': True,
                'checks': {name: False for name in CHECKS},
                'source_sha256': hashes, 'source_frame_counts': counts,
                'physical_source_shape': physical,
                'original_physical_acceptance_claimed': False,
                'legal_verdict_claimed': False}
    require(not synthetic and all(row.get('source_kind') == 'original_native_capture'
                                  for row in samples) and
            result.get('provenance_kind') == 'native',
            'Original Native speed source required')
    require(selection.get('manifest_sha256') == sha(manifest_path),
            'Original attempt selects an outdated delivery manifest')
    original = audit_original(attempt, REQUESTS[suffix])
    require(original['physical_speed_completion']['status'] == 'met',
            'Original speed passage not physically complete')
    review_path = source(attempt, 'speed-visibility-review.json')
    require(processing.get('original_source_hashes', {}).get('speed-visibility-review.json') ==
            sha(review_path), 'Independent pixel review source changed')
    review = read(review_path)
    require(review.get('format') == 'c111294-independent-speed-visibility-review-v1' and
            review.get('case_id') == case_id and review.get('original_pixels_reviewed') is True and
            review.get('reviewer') and review.get('method') and
            set(review.get('cameras', {})) == set(CAMERAS),
            'Independent original pixel review incomplete')
    for name in CAMERAS:
        item = review['cameras'][name]
        require(item.get('source_sha256') == hashes[name + '.mkv'] and
                item.get('frames') == 480 and item.get('vehicle_body_visible') is True and
                item.get('road_context_visible') is True,
                'Independent original pixel review incomplete: ' + name)
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'candidate_id': candidate_id, 'passed': True,
            'checks': {name: True for name in CHECKS},
            'source_sha256': {**hashes, 'speed-visibility-review.json': sha(review_path)},
            'source_frame_counts': counts, 'result_sha256': sha(result_path),
            'processing_sha256': sha(processing_path),
            'physical_audit': original, 'pixel_review_sha256': sha(review_path),
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior delivery audit output')
    result = audit(args.case, args.candidate, args.attempt,
                   args.processing, diagnostic=args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'passed': result['passed'],
                      'diagnostic': args.diagnostic}))


if __name__ == '__main__':
    main()
