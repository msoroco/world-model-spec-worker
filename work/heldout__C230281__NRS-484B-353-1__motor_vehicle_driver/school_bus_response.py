"""Source-bound school-bus signal and vehicle-motion measurements; no legal verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

STOP_TOLERANCE_MPS = 0.05  # measurement noise tolerance, not a statutory time limit


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
            other['premature_restart_frame'] >= base['red_cessation_frame']):
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
    parser.add_argument('--context', required=True)
    parser.add_argument('--signal', required=True)
    parser.add_argument('--motion', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(measure(args.context, args.signal, args.motion), indent=2)+'\n')


if __name__ == '__main__':
    main()
