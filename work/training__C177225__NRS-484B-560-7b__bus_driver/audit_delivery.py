"""Independent source audit for one saved directed-stop delivery attempt.

Diagnostic mode proves the audit's joins and rejection behavior. Only a Native
attempt with a source-bound visual review can pass delivery acceptance.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

VIEWS = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
ASSIGNMENT = 'training__C177225__NRS-484B-560-7b__bus_driver'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def read(root, name):
    return json.loads(source(root, name).read_text())


def rows(root, name):
    return [json.loads(line) for line in source(root, name).read_text().splitlines()
            if line.strip()]


def media(root, name, count):
    path = source(root, name + '.mkv')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                            '-select_streams', 'v:0', '-show_entries',
                            'stream=width,height,nb_read_frames,codec_name',
                            '-of', 'json', str(path)], capture_output=True,
                           text=True, check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('No unique delivery video stream: ' + name)
    item = streams[0]
    if ((item.get('width'), item.get('height')) != VIEWS[name] or
            item.get('codec_name') != 'ffv1' or
            int(item.get('nb_read_frames', -1)) != count):
        raise ValueError('Delivery video profile/frame mismatch: ' + name)
    # Decode the governing midpoint from the retained original, not a render.
    frame = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                            '-vf', f'select=eq(n\\,{count // 2})',
                            '-frames:v', '1', '-f', 'image2pipe',
                            '-vcodec', 'png', '-'], capture_output=True,
                           check=True, timeout=120)
    if not frame.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Governing delivery pixels did not decode: ' + name)
    return {'source': name + '.mkv', 'sha256': sha(path),
            'frame_count': count, 'governing_frame_decoded': count // 2,
            'sample_png_sha256': hashlib.sha256(frame.stdout).hexdigest()}


def audit(root, case_id, *, diagnostic=False):
    root = Path(root)
    config = read(root, 'config.json')
    result = read(root, 'result.json')
    provenance_source = ('acquisition-provenance.json' if diagnostic
                         else 'capture-seal.json')
    provenance = read(root, provenance_source)
    if (config.get('case_id') != case_id or result.get('case_id') != case_id or
            case_id not in (ASSIGNMENT + '__reference', ASSIGNMENT + '__contrast')):
        raise ValueError('Delivery case identity differs')
    if provenance.get('provenance_kind') != ('synthetic_fixture' if diagnostic else 'native'):
        raise ValueError('Delivery provenance differs from audit mode')
    if not diagnostic and (provenance.get('format') != 'worker-sealed-capture' or
                           provenance.get('restoration', {}).get('restored') is not True or
                           provenance.get('frames') != 600):
        raise ValueError('Original Native capture seal incomplete')
    if not diagnostic:
        sealed = provenance.get('sources', {})
        for name in ('config.json', 'officer_signal_definition.json',
                     'bus_native_rows.jsonl', 'officer_signal_rows.jsonl',
                     'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                     *(view + '.mkv' for view in VIEWS)):
            if sealed.get(name) != sha(source(root, name)):
                raise ValueError('Original Native sealed source changed: ' + name)
    count = config.get('frames')
    if count != 600 or config.get('rate_hz') != 20:
        raise ValueError('Delivery capture profile differs')
    signal = read(root, 'officer_signal_definition.json')
    bus = rows(root, 'bus_native_rows.jsonl')
    officer = rows(root, 'officer_signal_rows.jsonl')
    mapping = rows(root, 'video_frames.jsonl')
    trace = rows(root, 'trace.jsonl')
    evidence = rows(root, 'capture/evidence.jsonl')
    if not all(len(x) == count for x in (bus, officer, mapping, trace, evidence)):
        raise ValueError('Delivery time join lacks full 600-frame sources')
    direction = config['direction']
    if signal.get('direction') != direction or not signal.get('authorized'):
        raise ValueError('Directed officer source differs')
    stop_line = -7.0 * direction
    stopped = False
    crossed = False
    governing = 0
    for index, (b, o, m, t, e) in enumerate(zip(bus, officer, mapping, trace, evidence)):
        frame = m.get('native_frame')
        if (m.get('video_frame') != index or frame != b.get('native_frame') or
                frame != o.get('native_frame') or frame != t.get('frame') or
                frame != e.get('original_frame') or
                abs(m.get('time_s', -1) - t.get('time_s', -2)) > 1e-6 or
                abs(m.get('time_s', -1) - e.get('recording_time_s', -2)) > 1e-6):
            raise ValueError('Delivery frame/time source join differs')
        if (b.get('actor_id') != signal.get('bus_id') or
                o.get('actor_id') != signal.get('officer_id') or
                o.get('recipient_actor_id') != signal.get('bus_id') or
                o.get('crossing_id') != signal.get('crossing_id') or
                o.get('direction') != direction or not o.get('authorized')):
            raise ValueError('Delivery actor/signal source binding differs')
        values = b.get('velocity_native_xyz_mps')
        if not isinstance(values, list) or len(values) != 3 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise ValueError('Delivery bus velocity missing or invalid')
        speed = math.sqrt(sum(v * v for v in values))
        front_distance = direction * (stop_line - (b['station_m'] + direction * 6.0))
        if o.get('governing'):
            governing += 1
            stopped |= speed <= .05 and front_distance >= 0
            crossed |= front_distance < 0
    requested = case_id.endswith('__reference')
    if governing < 1 or (requested and not stopped) or (not requested and not crossed):
        raise ValueError('Delivery requested behavior lacks measured source support')
    targets = [item for item in result.get('target_checks', [])
               if item.get('target') == 'bus_obeys_officer_direction']
    if (len(targets) != 1 or targets[0].get('requested') is not requested or
            targets[0].get('measured') is not stopped or
            targets[0].get('matched') is not (stopped == requested) or
            result.get('maneuver_completed') is not crossed or
            result.get('provenance_kind') != provenance['provenance_kind'] or
            result.get('video_references') != [name + '.mkv' for name in VIEWS] or
            result.get('video_frame_map_reference') != 'video_frames.jsonl' or
            result.get('trace_reference') != 'trace.jsonl'):
        raise ValueError('Delivery result differs from independent raw-source measurement')
    views = {name: media(root, name, count) for name in VIEWS}
    visual = None
    if not diagnostic:
        visual = read(root, 'visual_review.json')
        if (visual.get('case_id') != case_id or
                not visual.get('reviewer_id') or not visual.get('reviewed_at') or
                visual.get('source_video_sha256') != {k: v['sha256'] for k, v in views.items()} or
                visual.get('bus_rows_sha256') != sha(root / 'bus_native_rows.jsonl') or
                visual.get('officer_rows_sha256') != sha(root / 'officer_signal_rows.jsonl') or
                visual.get('frame_map_sha256') != sha(root / 'video_frames.jsonl') or
                visual.get('rail_asset_blueprint') != config.get('rail_asset_blueprint') or
                visual.get('officer_gesture_visible') is not True or
                visual.get('rail_crossing_physically_verified') is not True or
                visual.get('reviewed_frames') != [1, count // 2, count]):
            raise ValueError('Original Native visual/rail review incomplete')
    return {'format': 'c177225-independent-delivery-audit-v1', 'case_id': case_id,
            'diagnostic_passed': True, 'delivery_accepted': not diagnostic,
            'provenance_kind': provenance['provenance_kind'],
            'checks_verified': ['all_participants', 'time_join',
                                'source_video_frame_counts', 'governing_pixel_decode',
                                'raw_motion_result_consistency'] +
                               ([] if diagnostic else ['native_source',
                                                        'visual_review_binding',
                                                        'physical_completion']),
            'checks_pending': (['original_native_source', 'officer_gesture_visibility',
                                'rail_crossing_physical_review'] if diagnostic else []),
            'source_sha256': {name: sha(source(root, name)) for name in (
                'config.json', 'result.json', provenance_source,
                'officer_signal_definition.json', 'bus_native_rows.jsonl',
                'officer_signal_rows.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                'capture/evidence.jsonl')},
            'video_sources': views, 'governing_frames': governing,
            'observed_stop_before_line': stopped, 'observed_crossing_entry': crossed,
            'visual_review': visual,
            'physical_acceptance_claimed': not diagnostic,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    proof = audit(args.attempt, args.case, diagnostic=args.diagnostic)
    target = Path(args.output)
    if target.exists():
        raise ValueError('Retain prior audit output')
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': proof['case_id'],
                      'diagnostic_passed': proof['diagnostic_passed'],
                      'delivery_accepted': proof['delivery_accepted']}))
