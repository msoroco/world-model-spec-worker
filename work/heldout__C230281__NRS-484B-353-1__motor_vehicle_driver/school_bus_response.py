"""Source-bound school-bus signal and vehicle-motion measurements; no legal verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

STOP_TOLERANCE_MPS = 0.05  # measurement noise tolerance, not a statutory time limit
FIRST_CASE_ID = 'heldout__C230281__NRS-484B-353-1__motor_vehicle_driver__meeting_stop'


def _sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original school-bus source: ' + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _roi(roi, width, height):
    if (not isinstance(roi, list) or len(roi) != 4 or
        any(type(v) is not int for v in roi)):
        raise ValueError('Lamp ROI must be four integer pixel coordinates')
    x0, y0, x1, y1 = roi
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError('Lamp ROI outside original camera')
    return roi


def _red_count(rgb, width, roi):
    x0, y0, x1, y1 = roi
    count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            offset = 3 * (y * width + x)
            red, green, blue = rgb[offset:offset + 3]
            count += red >= 160 and red >= 2 * green and red >= 2 * blue
    return count


def _video_red_counts(path, roi, expected_frames):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original school-bus camera: ' + str(path))
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-show_entries', 'stream=width,height', '-of', 'json', str(path)],
                           capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Original school-bus camera video stream missing')
    width, height = (streams[0].get('width'), streams[0].get('height'))
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise ValueError('Original school-bus camera dimensions invalid')
    _roi(roi, width, height)
    frame_bytes = width * height * 3
    decoder = subprocess.Popen(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(path),
                                '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    counts = []
    try:
        for _ in range(expected_frames + 1):
            frame = decoder.stdout.read(frame_bytes)
            if not frame:
                break
            if len(frame) != frame_bytes:
                raise ValueError('Original school-bus camera frame truncated')
            counts.append(_red_count(frame, width, roi))
        if len(counts) != expected_frames:
            raise ValueError('Original school-bus camera frame count differs from frame map')
    finally:
        decoder.stdout.close()
        if decoder.poll() is None:
            decoder.kill()
        decoder.wait()
    if decoder.returncode not in (0, -9):
        raise ValueError('Original school-bus camera decode failed')
    return counts


def audit_red_pixel_sources(frame_map_path, command_path, front_video_path,
                            rear_video_path, front_roi, rear_roi, min_red_pixels=8):
    """Compare source pixels with commands; ROI provenance still needs physical review."""
    frame_map = _rows(_jsonl(frame_map_path), 'frame map')
    commands = _rows(_jsonl(command_path), 'signal command')
    if [(r['frame'], r['time_s']) for r in frame_map] != [
            (r['frame'], r['time_s']) for r in commands]:
        raise ValueError('Original signal commands and frame map differ')
    if type(min_red_pixels) is not int or min_red_pixels < 1:
        raise ValueError('Red pixel threshold invalid')
    front = _video_red_counts(front_video_path, front_roi, len(frame_map))
    rear = _video_red_counts(rear_video_path, rear_roi, len(frame_map))
    rows = []
    for mapped, command, front_count, rear_count in zip(frame_map, commands, front, rear):
        operating = command.get('red_signal_commanded')
        phase = command.get('red_phase_commanded')
        if type(operating) is not bool or type(phase) is not bool or phase and not operating:
            raise ValueError('Original school-bus signal command invalid')
        front_candidate = front_count >= min_red_pixels
        rear_candidate = rear_count >= min_red_pixels
        rows.append({'frame': mapped['frame'], 'time_s': mapped['time_s'],
                     'red_phase_commanded': phase,
                     'front_red_pixel_count': front_count,
                     'rear_red_pixel_count': rear_count,
                     'front_red_candidate': front_candidate,
                     'rear_red_candidate': rear_candidate})
        if front_candidate != phase or rear_candidate != phase:
            raise ValueError('Original front/rear red pixels disagree with signal command')
    if not (sum(r['red_phase_commanded'] for r in rows) >= 2 and
            sum(not r['red_phase_commanded'] for r in rows) >= 2):
        raise ValueError('Original red on/off pixel contrast interval incomplete')
    sources = {'frame_map': frame_map_path, 'command': command_path,
               'front_video': front_video_path, 'rear_video': rear_video_path}
    return {'format': 'worker-school-bus-red-pixel-candidates',
            'source_sha256': {name: _sha_file(path)
                              for name, path in sources.items()},
            'front_roi': front_roi, 'rear_roi': rear_roi,
            'min_red_pixels': min_red_pixels, 'frames': rows,
            'roi_lamp_identity_reviewed': False,
            'front_rear_red_visibility_verified': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def audit_pupil_service_source(pupil_path, motion_path, purpose):
    """Reopen walker and bus motion originals; report a service-motion candidate."""
    if purpose not in ('receiving', 'discharging'):
        raise ValueError('School-bus pupil-service purpose invalid')
    pupil = _rows(_jsonl(pupil_path), 'pupil')
    motion = _rows(_jsonl(motion_path), 'motion')
    if [(r['frame'], r['time_s']) for r in pupil] != [
            (r['frame'], r['time_s']) for r in motion]:
        raise ValueError('Original pupil and bus motion frames differ')
    bus_ids = {r.get('bus_id') for r in pupil + motion}
    pupil_ids = {r.get('pupil_id') for r in pupil}
    if len(bus_ids) != 1 or None in bus_ids or len(pupil_ids) != 1 or None in pupil_ids:
        raise ValueError('Original pupil/bus identity differs')
    distances = []
    for pupil_row, motion_row in zip(pupil, motion):
        if pupil_row.get('requested_purpose') != purpose:
            raise ValueError('Original pupil purpose changed')
        speed = pupil_row.get('pupil_speed_mps')
        bus_speed = motion_row.get('bus_speed_mps')
        distance = pupil_row.get('pupil_distance_to_bus_m')
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in (speed, bus_speed, distance)):
            raise ValueError('Original pupil/bus motion readback invalid')
        if bus_speed > STOP_TOLERANCE_MPS:
            raise ValueError('Original school bus moved during pupil service')
        distances.append(distance)
    movement = distances[0] - min(distances) if purpose == 'receiving' else max(distances) - distances[0]
    if movement < 1.0 or not any(r['pupil_speed_mps'] > .2 for r in pupil):
        raise ValueError('Original pupil-service movement not observed')
    return {'format': 'worker-school-bus-pupil-service-candidate',
            'source_sha256': {'pupil': _sha_file(pupil_path), 'motion': _sha_file(motion_path)},
            'purpose': purpose, 'bus_id': next(iter(bus_ids)),
            'pupil_id': next(iter(pupil_ids)), 'distance_change_m': movement,
            'pupil_service_verified': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def audit_first_case_attempt(attempt, front_roi, rear_roi, purpose):
    """Reopen a whole first-case Native attempt and bind the two source audits."""
    attempt = Path(attempt)
    inventory_path = attempt / 'native-acquisition-inventory.json'
    inventory, inventory_sha = _read(inventory_path)
    if inventory.get('case_id') != FIRST_CASE_ID:
        raise ValueError('Original school-bus attempt case identity differs')
    required = ('motion_original.jsonl', 'pupil_original.jsonl',
                'signal_command_original.jsonl', 'video_frames.jsonl',
                'trace.jsonl', 'road.xodr', 'overview.mkv', 'approach.mkv',
                'reference_corner.mkv', 'driver_reference.mkv')
    declared = inventory.get('source_sha256')
    if not isinstance(declared, dict) or any(name not in declared for name in required):
        raise ValueError('Original school-bus source inventory incomplete')
    for name in required:
        path = attempt / name
        if not path.is_file() or not path.stat().st_size or _sha_file(path) != declared[name]:
            raise ValueError('Original school-bus source hash differs: ' + name)
    frame_map = _rows(_jsonl(attempt / 'video_frames.jsonl'), 'frame map')
    if inventory.get('frames') != [r['frame'] for r in frame_map]:
        raise ValueError('Original school-bus inventory frames differ')
    pixel = audit_red_pixel_sources(
        attempt / 'video_frames.jsonl', attempt / 'signal_command_original.jsonl',
        attempt / 'reference_corner.mkv', attempt / 'driver_reference.mkv',
        front_roi, rear_roi)
    pupil = audit_pupil_service_source(
        attempt / 'pupil_original.jsonl', attempt / 'motion_original.jsonl', purpose)
    return {'format': 'worker-school-bus-first-case-source-candidates',
            'case_id': FIRST_CASE_ID, 'inventory_sha256': inventory_sha,
            'source_sha256': {name: declared[name] for name in required},
            'red_pixels': pixel, 'pupil_motion': pupil,
            'bus_equipment_verified': False, 'undivided_road_verified': False,
            'pupil_service_verified': False,
            'front_rear_red_visibility_verified': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def _read(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original school-bus source: ' + str(path))
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(value, name):
    if not isinstance(value, list) or len(value) < 4:
        raise ValueError('Original ' + name + ' interval incomplete')
    frames = [r.get('frame') for r in value]
    times = [r.get('time_s') for r in value]
    if (any(type(f) is not int for f in frames) or frames != sorted(set(frames)) or
        any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or
        times != sorted(set(times))):
        raise ValueError('Original ' + name + ' frame/time order invalid')
    return value


def _gap(subject, bus, tangent):
    if (not isinstance(tangent, list) or len(tangent) != 2 or
        any(type(v) not in (int, float) or not math.isfinite(v) for v in tangent) or
        abs(math.hypot(*tangent)-1) > .01):
        raise ValueError('Original road tangent invalid')
    def values(corners):
        if (not isinstance(corners, list) or len(corners) != 4 or
            any(not isinstance(p, list) or len(p) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                for p in corners)):
            raise ValueError('Original body corners missing')
        return [p[0]*tangent[0]+p[1]*tangent[1] for p in corners]
    return min(values(subject))-max(values(bus))


def measure(context_path, signal_path, motion_path):
    context, csha = _read(context_path)
    signal, ssha = _read(signal_path)
    motion, msha = _read(motion_path)
    if (context.get('approach') not in ('meeting', 'overtaking') or
        not context.get('bus_id') or not context.get('subject_id') or
        context.get('bus_stopped') is not True or
        context.get('pupil_stop_purpose') not in (True, False, None) or
        context.get('signs_equipped') not in (True, False, None)):
        raise ValueError('Original bus/approach context incomplete')
    signal = _rows(signal, 'signal')
    motion = _rows(motion, 'motion')
    if [(r['frame'], r['time_s']) for r in signal] != [(r['frame'], r['time_s']) for r in motion]:
        raise ValueError('Original signal and motion frames differ')
    if any(r.get('bus_id') != context['bus_id'] for r in signal+motion):
        raise ValueError('Original bus identity differs')
    if any(r.get('subject_id') != context['subject_id'] for r in motion):
        raise ValueError('Original subject identity differs')
    operating = []
    phase = []
    gaps = []
    speeds = []
    for sig, row in zip(signal, motion):
        if (type(sig.get('red_signal_operating')) is not bool or
            type(sig.get('red_phase_on')) is not bool or
            type(sig.get('front_red_visible')) is not bool or
            type(sig.get('rear_red_visible')) is not bool):
            raise ValueError('Original front/rear signal state missing')
        if sig['red_phase_on'] and not sig['red_signal_operating']:
            raise ValueError('Red phase active after signal cessation')
        if sig['red_phase_on'] and not (sig['front_red_visible'] and sig['rear_red_visible']):
            raise ValueError('Flashing red not visible front and rear')
        speed = row.get('subject_speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original subject speed invalid')
        speeds.append(float(speed))
        gaps.append(_gap(row.get('subject_corners'), row.get('bus_corners'), row.get('travel_tangent_xy')))
        operating.append(sig['red_signal_operating'])
        phase.append(sig['red_phase_on'])
    onset = next((i for i, x in enumerate(operating) if x), None)
    if onset is None or onset == 0:
        raise ValueError('Original red onset missing')
    cessation = next((i for i in range(onset+1, len(operating)) if not operating[i]), None)
    if cessation is None or any(operating[i] for i in range(cessation, len(operating))):
        raise ValueError('Original red cessation missing or restarted')
    active_phase = phase[onset:cessation]
    if not (True in active_phase and False in active_phase and
            any(active_phase[i] != active_phase[i-1] for i in range(1, len(active_phase)))):
        raise ValueError('Original flashing red phase alternation missing')
    stop = next((i for i in range(onset, len(speeds)) if speeds[i] <= STOP_TOLERANCE_MPS), None)
    pass_frame = next((signal[i]['frame'] for i in range(onset, len(gaps)) if gaps[i] > 0), None)
    restart = next((signal[i]['frame'] for i in range((stop+1) if stop is not None else len(speeds), cessation)
                    if speeds[i] > STOP_TOLERANCE_MPS), None)
    held = stop is not None and stop < cessation and restart is None and all(
        speeds[i] <= STOP_TOLERANCE_MPS for i in range(stop, cessation))
    return {'format': 'worker-school-bus-original-response',
            'source_sha256': {'context': csha, 'signal': ssha, 'motion': msha},
            'approach': context['approach'], 'bus_id': context['bus_id'],
            'subject_id': context['subject_id'], 'red_onset_frame': signal[onset]['frame'],
            'red_cessation_frame': signal[cessation]['frame'],
            'first_stop_frame': signal[stop]['frame'] if stop is not None else None,
            'onset_to_stop_s': signal[stop]['time_s']-signal[onset]['time_s'] if stop is not None else None,
            'first_full_body_pass_frame': pass_frame,
            'premature_restart_frame': restart, 'held_stop_until_cessation': held,
            'signed_full_body_gap_m': [{'frame': r['frame'], 'value': gap} for r, gap in zip(motion, gaps)],
            'stop_tolerance_mps': STOP_TOLERANCE_MPS,
            'pupil_stop_purpose': context['pupil_stop_purpose'],
            'signs_equipped': context['signs_equipped'],
            'divided_other_roadway': context.get('divided_other_roadway'),
            'traffic_officer_control': context.get('traffic_officer_control'),
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def audit_motion_comparison(baseline_paths, variant_paths, kind):
    """Independently reopen originals and isolate the planned motion difference."""
    if kind not in ('premature_restart', 'pass_during_red'):
        raise ValueError('Unknown school-bus motion comparison')
    base = measure(*baseline_paths)
    other = measure(*variant_paths)
    if (base['source_sha256']['context'] != other['source_sha256']['context'] or
        base['source_sha256']['signal'] != other['source_sha256']['signal'] or
        base['bus_id'] != other['bus_id'] or base['subject_id'] != other['subject_id'] or
        base['approach'] != other['approach']):
        raise ValueError('School-bus comparison changed fixed original context/signal')
    if (not base['held_stop_until_cessation'] or
        base['first_full_body_pass_frame'] is None or
        base['first_full_body_pass_frame'] < base['red_cessation_frame']):
        raise ValueError('School-bus comparison baseline lacks held stop and post-red pass')
    if kind == 'premature_restart':
        if (other['first_stop_frame'] != base['first_stop_frame'] or
            other['premature_restart_frame'] is None or
            other['premature_restart_frame'] >= base['red_cessation_frame'] or
            other['first_full_body_pass_frame'] is None or
            other['first_full_body_pass_frame'] < base['red_cessation_frame']):
            raise ValueError('School-bus comparison lacks isolated early restart')
    else:
        if (other['first_full_body_pass_frame'] is None or
            other['first_full_body_pass_frame'] >= base['red_cessation_frame']):
            raise ValueError('School-bus comparison lacks passage during red')
    return {'format': 'worker-school-bus-motion-comparison', 'kind': kind,
            'fixed_source_sha256': {'context': base['source_sha256']['context'],
                                    'signal': base['source_sha256']['signal']},
            'baseline_motion_sha256': base['source_sha256']['motion'],
            'variant_motion_sha256': other['source_sha256']['motion'],
            'baseline': base, 'variant': other,
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--context')
    parser.add_argument('--signal')
    parser.add_argument('--motion')
    parser.add_argument('--frame-map')
    parser.add_argument('--command')
    parser.add_argument('--front-video')
    parser.add_argument('--rear-video')
    parser.add_argument('--front-roi', help='JSON [x0,y0,x1,y1] in original pixels')
    parser.add_argument('--rear-roi', help='JSON [x0,y0,x1,y1] in original pixels')
    parser.add_argument('--pupil-original')
    parser.add_argument('--pupil-purpose', choices=('receiving', 'discharging'))
    parser.add_argument('--attempt', help='Retained first-case Native source directory')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.attempt:
        if (not all((args.front_roi, args.rear_roi, args.pupil_purpose)) or any((
                args.context, args.signal, args.motion, args.frame_map,
                args.command, args.front_video, args.rear_video, args.pupil_original))):
            parser.error('Attempt audit requires retained directory, ROIs and pupil purpose')
        result = audit_first_case_attempt(
            args.attempt, json.loads(args.front_roi), json.loads(args.rear_roi),
            args.pupil_purpose)
    elif args.pupil_original:
        if (not args.motion or not args.pupil_purpose or any((
                args.context, args.signal, args.frame_map, args.command,
                args.front_video, args.rear_video, args.front_roi, args.rear_roi))):
            parser.error('Pupil audit requires pupil and motion originals and purpose')
        result = audit_pupil_service_source(args.pupil_original, args.motion,
                                            args.pupil_purpose)
    elif args.frame_map:
        required = (args.command, args.front_video, args.rear_video,
                    args.front_roi, args.rear_roi)
        if not all(required) or any((args.context, args.signal, args.motion,
                                    args.pupil_purpose)):
            parser.error('Pixel audit requires original frame map, command, both videos and ROIs')
        result = audit_red_pixel_sources(
            args.frame_map, args.command, args.front_video, args.rear_video,
            json.loads(args.front_roi), json.loads(args.rear_roi))
    else:
        if not all((args.context, args.signal, args.motion)) or any((
                args.command, args.front_video, args.rear_video, args.front_roi,
                args.rear_roi, args.pupil_purpose)):
            parser.error('Motion measurement requires context, signal and motion originals')
        result = measure(args.context, args.signal, args.motion)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
