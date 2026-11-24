"""Independent exact-case source audit; diagnostics never establish physical completion."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frames(path):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=nb_read_frames',
                          '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
                         text=True, capture_output=True, timeout=120)
    require(run.returncode == 0 and run.stdout.strip().isdigit(),
            'Original camera decode failed: ' + path.name)
    return int(run.stdout.strip())


def audit(case_id, attempt, processing_path, diagnostic, review_path=None):
    manifest = read(HERE / 'execution-manifest.json')
    require(manifest['assignment_id'] == HERE.name, 'Wrong assignment')
    entry = next((c for c in manifest['cases'] if c['case_id'] == case_id), None)
    require(entry is not None and entry['kind'] == 'delivery', 'Unselected case')
    require(sha(HERE / entry['construction']) == entry['construction_sha256'],
            'Selected construction hash differs')
    attempt = Path(attempt).resolve()
    processing_path = Path(processing_path).resolve()
    processing = read(processing_path)
    require(processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('passed') is True and
            processing.get('timestamp_joins', {}).get('frames') == 600 and
            processing.get('case_id') == case_id and
            processing.get('candidate_id') == 'primary' and
            processing.get('physical_acceptance_claimed') is False and
            processing.get('legal_acceptance_claimed') is False,
            'Saved processing source chain incomplete')
    selection = read(attempt / 'candidate-selection.json')
    require(selection.get('construction_sha256') == entry['construction_sha256'] and
            selection.get('candidate_id') == 'primary',
            'Original selection differs from exact construction')
    required = ('roundabout-speed-history.jsonl', 'roundabout-survey.json',
                'trace.jsonl', 'video_frames.jsonl', 'capture/manifest.json',
                'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                *(name + '.mkv' for name in CAMERAS))
    hashes = {}
    for name in required:
        path = attempt / name
        require(path.is_file(), 'Missing original source: ' + name)
        hashes[name] = sha(path)
        require(processing.get('original_source_hashes', {}).get(name) == hashes[name],
                'Saved original source hash differs: ' + name)
    counts = {name: frames(attempt / (name + '.mkv')) for name in CAMERAS}
    require(set(counts.values()) == {600}, 'Original camera frame count differs')
    rows = [json.loads(line) for line in
            (attempt / 'roundabout-speed-history.jsonl').read_text().splitlines()]
    require(len(rows) == 600 and all(row['video_frame'] == i and
            abs(row['time_s'] - i / 20) < 1e-6 for i, row in enumerate(rows)),
            'Original speed frame/time join differs')
    synthetic = all(row.get('synthetic_diagnostic') is True for row in rows)
    if diagnostic:
        require(synthetic, 'Expected synthetic CPU diagnostic source')
        return {'format': 'worker-delivery-diagnostic-audit', 'case_id': case_id,
                'source_shape_passed': True, 'physical_completion': False,
                'legal_acceptance': False, 'synthetic': True,
                'original_source_sha256': hashes, 'camera_frame_counts': counts,
                'selected_construction_sha256': entry['construction_sha256'],
                'processing_sha256': sha(processing_path)}
    require(not synthetic, 'Original Native roundabout source required')
    require(all(row.get('synthetic_diagnostic') is not True for row in rows),
            'Mixed diagnostic and original speed sources')
    require(len({row.get('subject_id') for row in rows}) == 1 and
            rows[0].get('subject_id') is not None,
            'Original subject identity incomplete')
    roads = [row.get('road_id') for row in rows]
    lanes = [row.get('lane_id') for row in rows]
    require(roads[0] == 1 and 2 in roads and roads[-1] == 2 and
            all(lane in (-1, -2) for lane in lanes),
            'Native roundabout arc/exit traversal incomplete')
    native_frames = [row.get('native_frame') for row in rows]
    require(all(isinstance(frame, int) for frame in native_frames) and
            all(a < b for a, b in zip(native_frames, native_frames[1:])),
            'Original Native frame progression incomplete')
    speeds = []
    for row in rows:
        vector = row.get('velocity_xyz_mps')
        require(isinstance(vector, list) and len(vector) == 3 and
                all(type(value) in (float, int) and math.isfinite(value)
                    for value in vector), 'Original velocity missing')
        speeds.append(math.sqrt(sum(value * value for value in vector)) *
                      2.2369362921)
    speed_requirement = (max(speeds) <= 80 if case_id.endswith('__controlled_1')
                         else max(speeds) > 80)
    require(speed_requirement, 'Measured original speed boundary not achieved')
    result_path = Path(processing.get('result', '')).resolve()
    require(result_path.is_file() and processing.get('result_sha256') ==
            sha(result_path), 'Saved Native result hash differs')
    result = read(result_path)
    require(result.get('case_id') == case_id and
            result.get('provenance_kind') == 'native' and
            result.get('legal_verdict_claimed') is not True,
            'Saved original result provenance differs')
    review_path = Path(review_path) if review_path else attempt / 'roundabout-visibility-review.json'
    require(review_path.is_file(), 'Independent original pixel review missing')
    review = read(review_path)
    require(review.get('format') == 'worker-roundabout-visibility-review' and
            review.get('case_id') == case_id and
            review.get('reviewer') and review.get('method') and
            review.get('original_pixels_reviewed') is True and
            review.get('roundabout_arc_exit_visible') is True and
            review.get('subject_visible') is True,
            'Independent original pixel review incomplete')
    for name in CAMERAS:
        item = review.get('cameras', {}).get(name, {})
        require(item.get('source_sha256') == hashes[name + '.mkv'] and
                item.get('frames') == 600 and
                item.get('vehicle_visible') is True and
                item.get('road_context_visible') is True,
                'Independent original camera review incomplete: ' + name)
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'passed': True, 'physical_completion': True,
            'legal_acceptance': False, 'synthetic': False,
            'checks': {key: True for key in ('native_source', 'all_participants',
                      'time_join', 'full_video_decode', 'actual_pixels',
                      'physical_completion')},
            'original_source_sha256': hashes,
            'camera_frame_counts': counts,
            'selected_construction_sha256': entry['construction_sha256'],
            'processing_sha256': sha(processing_path),
            'result_sha256': sha(result_path),
            'pixel_review_sha256': sha(review_path),
            'maximum_measured_mph': max(speeds)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior audit output')
    result = audit(args.case, args.attempt, args.processing,
                   args.diagnostic, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'source_shape_passed': result.get('source_shape_passed',
                                                       result.get('passed')),
                      'physical_completion': result['physical_completion']}))
