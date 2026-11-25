"""Independent source and pixel audit for one saved pedestrian crossing.

Diagnostic mode exercises the software on a synthetic fixture. Ordinary mode
requires original Native acquisition and a separate map/pixel review receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixels(path, width, height, hashes):
    size = width * height * 3
    process = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-vsync', '0', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for expected in hashes:
            frame = process.stdout.read(size)
            require(len(frame) == size, 'Camera source ended before original frame map')
            require(hashlib.sha256(frame).hexdigest() == expected,
                    'Original camera pixel hash differs')
        require(process.stdout.read(1) == b'', 'Camera source has extra frames')
        error = process.stderr.read().decode('utf-8', errors='replace')
        require(process.wait(timeout=60) == 0, 'Camera decode failed: ' + error[-300:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def audit(case, candidate, attempt, processing, diagnostic):
    attempt = Path(attempt).resolve()
    processing = read(processing)
    config = read(attempt / 'config.json')
    require(config['case_id'] == case and config['selected_case_id'] == case,
            'Exact case identity differs')
    require(config['duration_s'] == 30 and config['rate_hz'] == 20,
            'Complete crossing interval differs')
    require(processing['case_id'] == case and processing['candidate_id'] == candidate and
            processing['passed'] is True and processing['recorded_only'] is True and
            processing['originals_preserved'] is True, 'Saved processing receipt differs')
    selection = read(attempt / 'candidate-selection.json')
    require(selection['candidate_id'] == candidate and selection['case_id'] == case,
            'Selected candidate differs')
    require(sha(attempt / 'construction.json') == processing['native_revision']['construction_sha256'],
            'Original construction changed')
    for relative, digest in processing['original_source_hashes'].items():
        path = attempt / relative
        require(path.is_file() and sha(path) == digest,
                'Original acquisition changed: ' + relative)
    sample = rows(attempt / 'route-samples.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    native = rows(attempt / 'capture/native/frames.jsonl')
    require(all(len(x) == 600 for x in (sample, mapping, trace, evidence, native)),
            'Full original source interval missing')
    actor = sample[0]['pedestrian_id']
    for index, (s, m, t, e, n) in enumerate(zip(sample, mapping, trace, evidence, native)):
        frame = m['native_frame']
        require(frame == s['native_frame'] == m['carla_frame'] == t['frame'] ==
                e['original_frame'] == n['frame'] and m['video_frame'] == index,
                'Original Native frame join differs')
        require(s['pedestrian_id'] == actor == e['actor_id'],
                'Original subject identity differs')
        require(abs(s['time_s'] - m['time_s']) < 1e-4 and
                abs(t['time_s'] - m['time_s']) < 1e-4 and
                abs(e['recording_time_s'] - m['time_s']) < 1e-4,
                'Original timestamp join differs')
        require(all(abs(a-b) < .002 for a,b in zip(s['pedestrian_xy_m'], e['ego']['position_m'][:2])),
                'Original pedestrian pose differs')
        require(set(m['source_rgb_sha256']) == set(CAMERAS) and
                s['original_frame_sha256'] == m['source_rgb_sha256']['reference_corner'],
                'Original pixel hash join differs')
    context = read(attempt / 'route-context.json')
    result = read(attempt / 'result.json')
    require(result['case_id'] == case and result['accepted'] is False and
            result['legal_verdict_claimed'] is False,
            'Analysis assigned acceptance or a legal result')
    if diagnostic:
        require(context['source_kind'] == 'synthetic_cpu_fixture',
                'Diagnostic mode requires a synthetic fixture')
    else:
        require(context['source_kind'] == 'native_observation',
                'Original Native source required')
        review = read(attempt / 'independent-source-review.json')
        require(review.get('native_map_reviewed') is True and
                review.get('crosswalk_pixels_reviewed') is True and
                review.get('pedestrian_pixels_reviewed') is True and
                review.get('curb_entry_exit_reviewed') is True and
                review.get('frame_count') == 600,
                'Independent original map, body, curb and crosswalk review required')
        require(review.get('reviewer') and review.get('source_hashes') and
                all(sha(attempt / name) == digest for name,digest in review['source_hashes'].items()),
                'Independent original review lacks source hashes')
        require(result['physical_checks']['maneuver']['status'] == 'met',
                'Physical crossing completion not established')
    for name, (width, height) in CAMERAS.items():
        pixels(attempt / (name + '.mkv'), width, height,
               [m['source_rgb_sha256'][name] for m in mapping])
    return {'format': 'worker-crossing-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'diagnostic': diagnostic, 'passed': True,
            'frames': 600, 'cameras': list(CAMERAS), 'original_native_accepted': not diagnostic,
            'legal_verdict_claimed': False,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
