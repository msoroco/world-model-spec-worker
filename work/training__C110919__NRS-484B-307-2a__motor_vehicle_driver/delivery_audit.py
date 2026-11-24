"""Audit retained right-turn source joins and physical review without legal labels."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def audit(case: str, attempt: Path, mode: str, pixel_review: Path | None,
          exclude_source: str | None) -> dict:
    attempt = attempt.resolve()
    required = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
                'native_samples.jsonl', 'body_history.jsonl', 'road_geometry.json',
                'capture/manifest.json', 'analysis-report.json', 'result.json')
    if exclude_source in required:
        raise ValueError('Missing source: ' + Path(exclude_source).name)
    paths = {name: attempt / name for name in required}
    if any(not path.is_file() for path in paths.values()):
        missing = next(name for name, path in paths.items() if not path.is_file())
        raise ValueError('Missing source: ' + Path(missing).name)
    trace, evidence, mapping, native, body = [rows(paths[name]) for name in required[:5]]
    if any(len(group) != 600 for group in (trace, evidence, mapping, native, body)):
        raise ValueError('Original source frame count differs')
    for index, (t, e, m, n, b) in enumerate(zip(trace, evidence, mapping, native, body)):
        frame = m.get('native_frame')
        if (m.get('video_frame') != index or frame != t.get('frame') or
            frame != e.get('original_frame') or frame != n.get('native_frame') or
            frame != b.get('frame')):
            raise ValueError('Original source frame join differs')
        if abs(m['time_s'] - n['time_s']) > 1e-4:
            raise ValueError('Original source timestamp join differs')
    capture = json.loads(paths['capture/manifest.json'].read_text())
    if not capture.get('extraction_confirmed') or capture.get('frames') != 600:
        raise ValueError('Original capture extraction incomplete')
    for name, expected in capture.get('sources', {}).items():
        if sha(attempt / name) != expected:
            raise ValueError('Capture source hash differs: ' + name)
    decoded = {}
    for camera in CAMERAS:
        video = attempt / (camera + '.mkv')
        if not video.is_file():
            raise ValueError('Missing source camera: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(video)],
            text=True, capture_output=True, timeout=120)
        if probe.returncode or probe.stdout.strip() != '600':
            raise ValueError('Source camera decode differs: ' + camera)
        decoded[camera] = {'frames': 600, 'sha256': sha(video)}
    analysis = json.loads(paths['analysis-report.json'].read_text())
    result = json.loads(paths['result.json'].read_text())
    if analysis.get('case_id') != case or result.get('case_id') != case:
        raise ValueError('Wrong exact case in saved source')
    if not result.get('maneuver_completed') or not result.get('target_checks'):
        raise ValueError('Original saved maneuver or target missing')
    diagnostic = capture.get('synthetic_diagnostic') is True
    if mode == 'diagnostic':
        if not diagnostic:
            raise ValueError('Diagnostic mode requires declared synthetic source')
        physical = False
    else:
        if diagnostic or result.get('provenance_kind') != 'native':
            raise ValueError('Synthetic fixture cannot be physical')
        capture_report = attempt / 'native-capture-report.json'
        if not capture_report.is_file():
            raise ValueError('Missing original Native capture report')
        native_report = json.loads(capture_report.read_text())
        if (native_report.get('case_id') != case or native_report.get('frames') != 600 or
            native_report.get('error') is not None or not native_report.get('restoration')):
            raise ValueError('Original Native capture or restoration incomplete')
        if pixel_review is None or not pixel_review.is_file():
            raise ValueError('Missing independent pixel review')
        review = json.loads(pixel_review.read_text())
        expected = {name: sha(attempt / name) for name in required}
        expected.update({camera + '.mkv': decoded[camera]['sha256'] for camera in CAMERAS})
        expected['native-capture-report.json'] = sha(capture_report)
        if review.get('case_id') != case or review.get('source_hashes') != expected:
            raise ValueError('Pixel review is not bound to these originals')
        findings = review.get('findings', {})
        needed = ('governing_circular_green_visible', 'no_turn_prohibition_visible',
                  'pedestrian_lawful_context_reviewed', 'vehicle_lawful_context_reviewed',
                  'full_body_and_conflict_visible', 'yield_timing_reviewed')
        if not review.get('reviewer') or any(findings.get(name) is not True for name in needed):
            raise ValueError('Independent physical pixel findings incomplete')
        physical = True
    return {'format': 'worker-right-turn-delivery-audit', 'case_id': case,
            'mode': mode, 'frames': 600, 'source_hashes': {name: sha(path) for name, path in paths.items()},
            'camera_decode': decoded, 'physical_checks_passed': physical,
            'legal_verdict_claimed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--mode', choices=('diagnostic', 'physical'), required=True)
    parser.add_argument('--pixel-review-file', type=Path)
    parser.add_argument('--exclude-source')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.mode,
                           args.pixel_review_file, args.exclude_source), indent=2))
