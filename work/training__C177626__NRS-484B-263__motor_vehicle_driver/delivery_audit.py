"""Independent saved-source audit for the controlled-access entry comparison.

Diagnostic mode verifies software provenance only. Original mode additionally
requires a source-hashed independent review of authority, pixels and motion.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))

ASSIGNMENT = 'training__C177626__NRS-484B-263__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native_samples.jsonl', 'camera_frames.jsonl', 'entry_history.jsonl',
           'authored-context.json', 'capture-seal.json', 'trace.jsonl',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(case, attempt, processing, diagnostic=False, review=None):
    attempt = Path(attempt)
    report = read(processing)
    require(case in (ASSIGNMENT + '__selected_ed45c8e4__condition_a',
                     ASSIGNMENT + '__selected_ed45c8e4__condition_b') and
            report.get('case_id') == case, 'Exact selected case differs')
    require(report.get('format') == 'worker-saved-processing' and report.get('passed') is True and
            report.get('recorded_only') is True and report.get('originals_preserved') is True and
            report.get('events') == ['saved_processing_started', 'selected_analysis_executed', 'originals_verified'] and
            report.get('timestamp_joins', {}).get('passed') is True and
            report['timestamp_joins'].get('frames') == 600 and
            report.get('missing_evidence') is False and
            report.get('physical_acceptance_claimed') is False and
            report.get('legal_acceptance_claimed') is False,
            'Saved lifecycle or complete source join differs')
    selection = read(attempt / 'candidate-selection.json')
    require(selection.get('case_id') == case and
            selection.get('candidate_id') == report.get('candidate_id') and
            selection.get('construction_sha256') == digest(attempt / 'construction.json'),
            'Selected construction differs from original')
    hashes = report.get('original_source_hashes', {})
    for name in (*SOURCES, *(view + '.mkv' for view in VIEWS)):
        path = attempt / name
        require(path.is_file() and hashes.get(name) == digest(path),
                'Original source missing or stale: ' + name)
    actors = rows(attempt / 'native_samples.jsonl')
    cameras = rows(attempt / 'camera_frames.jsonl')
    history = rows(attempt / 'entry_history.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    require(all(len(stream) == 600 for stream in (actors, cameras, history, mapping, trace, evidence)),
            'Original actor, camera or frame source incomplete')
    for index, (actor, camera, road, frame, motion, event) in enumerate(
            zip(actors, cameras, history, mapping, trace, evidence)):
        source_frame = actor.get('native_frame')
        require(actor.get('frame') == frame.get('video_frame') == index and
                frame.get('native_frame') == source_frame == camera.get('frame') ==
                road.get('frame') == motion.get('frame') == event.get('original_frame') and
                abs(actor.get('native_elapsed_s', -2) - frame.get('time_s', -1)) < 1e-4 and
                set(actor.get('traffic', {})) == {'near', 'far'} and
                set(camera.get('views', {})) == set(VIEWS),
                'Original all-participant or time join differs')
    result_path = Path(report.get('result', ''))
    require(result_path.is_file() and digest(result_path) == report.get('result_sha256'),
            'Saved measured result missing or changed')
    result = read(result_path)
    require(result.get('case_id') == case and result.get('video_frame_map_reference') == 'video_frames.jsonl' and
            result.get('legal_verdict_claimed') is False,
            'Saved physical check or legal boundary differs')
    from worker_exchange.native_output import assess_physical
    physical = assess_physical(attempt, read(attempt / 'config.json'))
    require(physical['physical_checks']['maneuver']['method'] and
            physical['physical_checks']['maneuver']['sources'],
            'Original road-transition evidence unavailable')
    decode = report.get('final_video_checks', {})
    require(decode.get('format') == 'source-decode' and decode.get('passed') is True and
            decode.get('frames') == 600 and decode.get('rgb_sequence_sha256'),
            'Full primary video decode missing')
    if not diagnostic:
        require(review is not None, 'Original physical and authority review required')
        checked = read(review)
        require(checked.get('case_id') == case and checked.get('source_hashes') == {
            name: hashes[name] for name in SOURCES} and
            all(checked.get(key) is True for key in
                ('controlled_access_authority_reviewed', 'all_participants_reviewed',
                 'actual_pixels_reviewed', 'physical_completion_reviewed')),
            'Original authority, all-participant, pixel or physical review incomplete')
        require(result.get('provenance_kind') == 'native' and result.get('diagnostic_fixture') is False and
                physical['physical_checks']['maneuver']['status'] == 'met',
                'Original Native physical completion unverified')
    return {'format': 'worker-c177626-delivery-audit', 'case_id': case,
            'source_sha256': {name: hashes[name] for name in SOURCES},
            'camera_sha256': {view: hashes[view + '.mkv'] for view in VIEWS},
            'frame_count': 600, 'diagnostic_fixture': diagnostic,
            'original_review_complete': not diagnostic, 'passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--review')
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.attempt, args.processing, args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'passed': True,
                      'diagnostic_fixture': args.diagnostic}))
