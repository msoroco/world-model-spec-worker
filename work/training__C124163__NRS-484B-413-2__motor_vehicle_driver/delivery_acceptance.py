"""Independent saved source audit for exact signal-distance cases."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def need(root, name):
    path = root/name
    if not path.is_file():
        raise ValueError('Missing delivery source: '+name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(root, case, diagnostic):
    root = Path(root)
    config = json.loads(need(root, 'config.json').read_text())
    if config['case_id'] != case:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        need(root, 'capture-seal.json')
        need(root, 'native-capture-report.json')
        review = json.loads(need(root, 'original-review.json').read_text())
        if not all(review.get(key) is True for key in
                   ('district_verified', 'weather_verified', 'turn_onset_verified',
                    'signal_pixels_reviewed', 'all_participants_verified')):
            raise ValueError('Independent original source review incomplete')
    names = ('signal-source.jsonl', 'context-review.json', 'trace.jsonl',
             'video_frames.jsonl', 'capture/evidence.jsonl')
    evidence = {name: sha(need(root, name)) for name in names}
    signal, trace, frames, capture = (rows(root/name) for name in
                                      (names[0], names[2], names[3], names[4]))
    if any(len(stream) != 600 for stream in (signal, trace, frames, capture)):
        raise ValueError('Incomplete 600-frame delivery source')
    context = json.loads((root/'context-review.json').read_text())
    if diagnostic and context.get('review_kind') != 'synthetic_diagnostic':
        raise ValueError('Diagnostic source provenance differs')
    for i, (source, state, mapping, event) in enumerate(zip(signal, trace, frames, capture)):
        native = source.get('native_frame')
        if (source.get('video_frame') != i or state.get('frame') != native
                or mapping.get('native_frame') != native
                or event.get('original_frame') != native
                or any(mapping['camera_native_frames'].get(view) != native for view in VIEWS)):
            raise ValueError('Original signal and camera frame join failed')
        if source.get('source_kind') != ('synthetic_native_sample' if diagnostic else 'original_post_tick_native'):
            raise ValueError('Signal source provenance differs')
    for view in VIEWS:
        path = need(root, view+'.mkv')
        run = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                              '-count_frames', '-show_entries', 'stream=nb_read_frames',
                              '-of', 'default=nw=1:nk=1', str(path)],
                             capture_output=True, text=True, check=True)
        if int(run.stdout.strip()) != 600:
            raise ValueError('Incomplete source video: '+view)
        evidence[view+'.mkv'] = sha(path)
        if not diagnostic and review['camera_sha256'][view] != evidence[view+'.mkv']:
            raise ValueError('Independent pixel review camera hash changed')
    return {'format': 'c124163-independent-delivery-audit-v1',
            'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': evidence, 'frames': 600,
            'diagnostic_fixture': diagnostic,
            'original_native_observed': not diagnostic,
            'display_pixels_reviewed': False if diagnostic else True,
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('attempt', 'case', 'output'):
        parser.add_argument('--'+key, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'case_id': args.case, 'frames': 600,
                      'diagnostic_fixture': args.diagnostic,
                      'physical_acceptance': False}))
