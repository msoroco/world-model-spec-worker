"""Independent source-bound audit for one 257(2) selected delivery attempt."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.name + '__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'entrance_controls.json', 'nonthrough_saved_packet.json',
           'trace.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl',
           'acquisition-provenance.json')


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
    require(case.startswith(BASE), 'Different exact selected case')
    manifest = read(HERE / 'execution-manifest.json')
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case]
    require(len(entries) == 1, 'Case is not an exact selected delivery entry')
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
    traces = rows(attempt / 'trace.jsonl')
    mappings = rows(attempt / 'video_frames.jsonl')
    captures = rows(attempt / 'capture/evidence.jsonl')
    packet = read(attempt / 'nonthrough_saved_packet.json')
    frames = packet['frames']
    require(all(len(seq) == 600 for seq in (traces, mappings, captures, frames)),
            'Six hundred original samples required for every participant')
    require(receipt.get('timestamp_joins', {}).get('frames') == 600
            and receipt['timestamp_joins'].get('passed') is True,
            'Original frame time join incomplete')
    require(receipt.get('final_video_checks', {}).get('frames') == 600
            and receipt['final_video_checks'].get('passed') is True,
            'Final video decode receipt incomplete')
    for index, (trace, mapping, capture, frame) in enumerate(zip(traces, mappings, captures, frames)):
        require(frame.get('frame') == index and frame.get('native_frame') == trace.get('frame')
                and mapping.get('carla_frame') == trace.get('frame')
                and abs(mapping.get('time_s', -1) - frame.get('t_s', -2)) < 1e-6
                and capture.get('original_frame') == trace.get('frame'),
                'Original Core/body/video join differs')
        require(len(frame.get('subject_body_vertices_m', [])) >= 4
                and len(frame.get('counterpart_body_vertices_m', [])) >= 4,
                'Original participant body source missing')
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
    controls = read(attempt / 'entrance_controls.json')
    require(controls.get('map_readback_sha256') == sha(attempt / 'road.xodr'),
            'Original map/control hash differs')
    if diagnostic:
        require(provenance.get('diagnostic_fixture') is True
                and provenance.get('native_executed') is False
                and result.get('provenance_kind') == 'synthetic_fixture',
                'Diagnostic fixture provenance changed')
    else:
        require(provenance.get('diagnostic_fixture') is False
                and provenance.get('native_executed') is True
                and result.get('provenance_kind') == 'native',
                'Original Native acquisition required')
        if controls.get('stop_reference') == 'nearest_viewpoint':
            rays = read(attempt / 'viewpoint_sight_rays.json')
            require(len(rays) == 600 and controls.get('viewpoint_sight_rays_sha256') ==
                    sha(attempt / 'viewpoint_sight_rays.json'),
                    'Original viewpoint sight rays missing or stale')
        if controls.get('control_exception'):
            states = read(attempt / 'control_state_frames.json')
            require(len(states) == 600 and controls.get('control_state_frames_sha256') ==
                    sha(attempt / 'control_state_frames.json'),
                    'Original officer/signal state missing or stale')
        review = read(attempt / 'independent-original-review.json')
        require(review.get('case_id') == case and
                review.get('source_kind') == 'independent_original_capture_review',
                'Independent original review missing')
        for check in ('native_source', 'all_participants', 'time_join', 'full_video_decode',
                      'actual_pixels', 'physical_completion'):
            require(review.get(check) is True, 'Independent original check missing: ' + check)
    return {'case_id': case, 'diagnostic_only': diagnostic,
            'joined_frames': 600, 'decoded_views': len(VIEWS),
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
