"""Independent source audit for one selected roundabout exit recording."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'roundabout-map-readback.json', 'native-raw-actors.jsonl',
           'control-intent.jsonl', 'trace.jsonl', 'video_frames.jsonl',
           'capture/evidence.jsonl', 'acquisition-provenance.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    require(path.is_file(), 'Missing original source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    require(path.is_file(), 'Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(case, attempt, processing, diagnostic=False, missing_source=None):
    require(case.startswith(PREFIX), 'Different exact selected case')
    manifest = read(HERE / 'execution-manifest.json')
    require(sum(entry['case_id'] == case for entry in manifest['cases']) == 1,
            'Case is not an exact selected delivery entry')
    attempt = Path(attempt).resolve()
    receipt = read(Path(processing))
    require(receipt.get('case_id') == case and receipt.get('candidate_id') == 'primary'
            and receipt.get('passed') is True and receipt.get('recorded_only') is True
            and receipt.get('originals_preserved') is True,
            'Recorded-only original receipt incomplete')
    hashes = receipt.get('original_source_hashes', {})
    for name in (*SOURCES, *(view + '.mkv' for view in VIEWS)):
        path = attempt / name if name != missing_source else attempt / 'missing-original-source'
        require(path.is_file(), 'Missing original source: ' + name)
        require(hashes.get(name) == sha(path), 'Original source hash differs: ' + name)
    actors = rows(attempt / 'native-raw-actors.jsonl')
    controls = rows(attempt / 'control-intent.jsonl')
    traces = rows(attempt / 'trace.jsonl')
    mappings = rows(attempt / 'video_frames.jsonl')
    captures = rows(attempt / 'capture/evidence.jsonl')
    require(all(len(seq) == 600 for seq in (actors, controls, traces, mappings, captures)),
            'Six hundred original samples required for subject and cameras')
    require(receipt.get('timestamp_joins', {}).get('frames') == 600
            and receipt['timestamp_joins'].get('passed') is True,
            'Original frame time join incomplete')
    require(receipt.get('final_video_checks', {}).get('frames') == 600
            and receipt['final_video_checks'].get('passed') is True,
            'Final video decode receipt incomplete')
    expected_intent = 'right_turn'
    for index, (actor, control, trace, mapping, capture) in enumerate(
            zip(actors, controls, traces, mappings, captures)):
        frame = trace.get('frame')
        require(actor.get('case_id') == case and actor.get('video_frame') == index
                and control.get('video_frame') == index
                and actor.get('native_frame') == control.get('native_frame') == frame
                and mapping.get('carla_frame') == frame and mapping.get('video_frame') == index
                and capture.get('original_frame') == frame
                and abs(mapping.get('time_s', -1) - trace.get('time_s', -2)) < 1e-6
                and abs(actor.get('time_s', -1) - trace.get('time_s', -2)) < 1e-6
                and abs(control.get('time_s', -1) - trace.get('time_s', -2)) < 1e-6,
                'Original actor/control/Core/video join differs')
        require(control.get('exit_intent') == expected_intent,
                'Original exit intent differs from selected case')
        participants = actor.get('actors', [])
        require(len(participants) == 1 and participants[0].get('role') == 'ego'
                and isinstance(participants[0].get('road_id'), int)
                and isinstance(participants[0].get('lane_id'), int)
                and len(capture.get('original_observations', {}).get('participants', [])) == 1,
                'Original participant map/body source missing')
        cameras = mapping.get('camera_native_frames', {})
        require(set(cameras) == set(VIEWS) and all(v == frame for v in cameras.values()),
                'Original four-camera frame synchronization differs')
    map_source = read(attempt / 'roundabout-map-readback.json')
    require({item['road_id'] for item in map_source.get('samples', [])} >= set(range(1, 9)),
            'Original eight-road roundabout map readback missing')
    for view in VIEWS:
        probe = subprocess.run(('ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'default=nokey=1:noprint_wrappers=1',
                                str(attempt / (view + '.mkv'))),
                               capture_output=True, text=True, check=True)
        require(probe.stdout.strip() == '600', 'Full original video decode differs: ' + view)
    result = read(Path(receipt['result']))
    require(result.get('case_id') == case and result.get('legal_verdict_claimed') is False
            and result.get('physical_acceptance_claimed') is False,
            'Finalizer asserted legal or physical acceptance')
    require(result.get('physical_checks', {}).get('maneuver', {}).get('status') in
            {'met', 'not_met', 'unverified'}, 'Physical completion is not source assessed')
    provenance = read(attempt / 'acquisition-provenance.json')
    if diagnostic:
        require(provenance.get('provenance_kind') == 'synthetic_fixture'
                and provenance.get('native_executed') is False
                and result.get('provenance_kind') == 'synthetic_fixture',
                'Diagnostic fixture provenance changed')
    else:
        require(provenance.get('provenance_kind') == 'native'
                and provenance.get('native_executed') is True
                and result.get('provenance_kind') == 'native',
                'Original Native acquisition required')
        review = read(attempt / 'independent-original-review.json')
        require(review.get('case_id') == case and
                review.get('source_kind') == 'independent_original_capture_review',
                'Independent original review missing')
        for check in ('native_source', 'all_participants', 'time_join', 'full_video_decode',
                      'actual_pixels', 'physical_completion'):
            require(review.get(check) is True, 'Independent original check missing: ' + check)
    return {'case_id': case, 'diagnostic_only': diagnostic, 'joined_frames': 600,
            'decoded_views': len(VIEWS),
            'physical_status': result['physical_checks']['maneuver']['status'],
            'legal_or_physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--missing-source')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.processing,
                           args.diagnostic, args.missing_source), sort_keys=True))
