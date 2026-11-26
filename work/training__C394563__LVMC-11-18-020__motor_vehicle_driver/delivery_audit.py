"""Independent saved-source audit of one exact signed school-crossing case."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
SOURCES = ('road_geometry.json', 'native_samples.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'body_history.jsonl', *VIDEOS)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path: Path) -> dict:
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())

def rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]

def audit(case: str, attempt: Path, processing: Path, diagnostic: bool,
          omit_source: str | None) -> dict:
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    saved = read(processing)
    if (saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
            saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256'] or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('passed') is not True):
        raise ValueError('Selected saved processing or full-frame decode differs')
    stage = Path(saved['analysis_directory']).resolve()
    if stage != processing.resolve().parent / 'analysis':
        raise ValueError('Saved analysis path escapes selected version')
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError('Missing source: ' + name)
        path = stage / name
        if not path.is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(path)
        if saved.get('original_source_hashes', {}).get(name) != hashes[name]:
            raise ValueError('Original source changed: ' + name)
    samples = rows(stage / 'native_samples.jsonl')
    frames = rows(stage / 'video_frames.jsonl')
    trace = rows(stage / 'trace.jsonl')
    body = rows(stage / 'body_history.jsonl')
    if len(samples) != len(frames) or len(samples) != len(trace) or len(samples) != len(body) or len(samples) != 600:
        raise ValueError('Incomplete participant/trace/frame history')
    if any(sample.get('native_frame') != frame.get('native_frame') for sample, frame in zip(samples, frames)):
        raise ValueError('Original source frame join changed')
    if len({s.get('person', {}).get('actor_id') for s in samples}) != 1:
        raise ValueError('Original person identity changed')
    for name in VIDEOS:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'default=noprint_wrappers=1:nokey=1', str(stage / name)],
                               capture_output=True, text=True, timeout=60)
        if probe.returncode != 0 or probe.stdout.strip() != '600':
            raise ValueError('Original four-view pixels do not decode: ' + name)
    road = read(stage / 'road_geometry.json')
    crosswalk = road['crosswalk']
    sign = road['school_xing_sign']
    if (abs(crosswalk['width_along_road_m'] - 3.6576) > 0.05 or
            sign['legend'] != 'School-Xing' or sign['x_m'] > -30.48 or
            crosswalk['near_x_m'] != 0 or not crosswalk['marked_yellow']):
        raise ValueError('Source school crossing geometry differs')
    report = read(stage / 'analysis-report.json')
    if report.get('case_id') != case or report.get('analysis_complete') is not True:
        raise ValueError('Wrong or incomplete saved analysis')
    for key in ('school_marking_context', 'signed_school_crossing_entry', 'reviewed_school_entry'):
        if report.get('measurements', {}).get(key, {}).get('method') is None:
            raise ValueError('Missing source-bound selected measurement: ' + key)
        for name, value in report['measurements'][key]['sources'].items():
            if name in hashes and value != hashes[name]:
                raise ValueError('Selected measurement source changed: ' + name)
    measured = report['measurements']['signed_school_crossing_entry']['value']['entry']
    if measured.get('native_frame') not in {s['native_frame'] for s in samples}:
        raise ValueError('Measured front entry lacks original frame')
    if diagnostic:
        receipt = read(attempt / 'compatibility.json')
        if receipt.get('construction_sha256') != entry['construction_sha256'] or receipt.get('passed') is not True:
            raise ValueError('Diagnostic compatibility identity differs')
        if report.get('diagnostic_fixture') is not True or report.get('physical_acceptance_claimed') is not False:
            raise ValueError('Diagnostic provenance differs')
    else:
        original = read(attempt / 'acquisition-provenance.json')
        review = read(stage / 'school-crossing-source-review.json')
        if original.get('provenance_kind') != 'native' or original.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        if (review.get('review_status') != 'independently_reviewed' or not review.get('reviewer') or
                review.get('city_engineer_authority_verified') is not True or
                review.get('displayed_school_xing_pixels_sha256') != hashes['overview.mkv'] or
                review.get('person_attempt_to_cross_verified') is not True or
                review.get('approach_side_verified') is not True):
            raise ValueError('Independent original school-crossing source review incomplete')
        physical = read(stage / 'result.json').get('physical_checks', {}).get('maneuver', {})
        if physical.get('status') != 'met':
            raise ValueError('Original physical entry completion unverified')
    return {'format': 'c394563-independent-delivery-audit-v1', 'case_id': case,
            'construction_sha256': entry['construction_sha256'], 'saved_processing_sha256': sha(processing),
            'source_sha256': hashes, 'observed_entry': measured,
            'checks': ['native_source_binding', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixel_bytes', 'physical_completion_rule'],
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--processing', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--diagnostic', action='store_true')
    p.add_argument('--omit-source', choices=SOURCES)
    a = p.parse_args()
    result = audit(a.case, a.attempt, a.processing, a.diagnostic, a.omit_source)
    if a.output.exists():
        raise ValueError('Audit output already exists')
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': a.case, 'diagnostic_only': a.diagnostic}))
