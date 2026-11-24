"""Source-shaped 20 Hz sidewalk encounter diagnostic; no legal verdict.

The diagnostic rows stand in for Native transform, footprint and synchronized
microphone packets. They are generated only for CPU measurement testing.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HZ = 20
FRAMES = 600
HALF_RIDER = 0.45
HALF_PEDESTRIAN = 0.35


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, signal_frame, yield_stop=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        for frame in range(FRAMES):
            time_s = frame / HZ
            ped_x = -1 + 0.9 * time_s
            # A requested pause is a controller test, not actual yielding.
            moving_time = max(0.0, time_s - (1.5 if yield_stop and time_s > 4 else 0))
            rider_x = -9 + 1.4 * moving_time
            rider_speed = 0.0 if yield_stop and 4 <= time_s < 5.5 else 1.4
            # Four synthetic microphone samples per frame at pedestrian location.
            pulse = signal_frame is not None and signal_frame <= frame < signal_frame + 6
            audio = [0.2 + (1.2 if pulse else 0.0) * math.sin(k * math.pi / 2)
                     for k in range(4)]
            row = {'native_frame': 10000 + frame, 'time_s': time_s,
                   'rider_id': 17, 'pedestrian_id': 19,
                   'rider_device_class': 'electric_scooter',
                   'sidewalk_polygon_xy_m': [[-20, -1.5], [50, -1.5], [50, 1.5], [-20, 1.5]],
                   'rider_center_xy_m': [rider_x, -0.55],
                   'rider_footprint_xy_m': [[rider_x-HALF_RIDER, -0.8],
                                           [rider_x+HALF_RIDER, -0.8],
                                           [rider_x+HALF_RIDER, -0.3],
                                           [rider_x-HALF_RIDER, -0.3]],
                   'rider_speed_mps': rider_speed,
                   'pedestrian_center_xy_m': [ped_x, 0.55],
                   'pedestrian_footprint_xy_m': [[ped_x-HALF_PEDESTRIAN, 0.3],
                                                [ped_x+HALF_PEDESTRIAN, 0.3],
                                                [ped_x+HALF_PEDESTRIAN, 0.8],
                                                [ped_x-HALF_PEDESTRIAN, 0.8]],
                   'pedestrian_speed_mps': 0.9,
                   'microphone_at_pedestrian_pcm': audio,
                   'microphone_calibration': 'synthetic_relative_amplitude',
                   'signal_controller_request': pulse}
            stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


def read_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Expected 600 original source frames')
    for index, row in enumerate(rows):
        if row['native_frame'] != 10000 + index or abs(row['time_s'] - index / HZ) > 1e-8:
            raise ValueError('Original frame and time join failed')
        if row['rider_id'] == row['pedestrian_id']:
            raise ValueError('Rider and pedestrian must be distinct')
        if len(row['microphone_at_pedestrian_pcm']) != 4:
            raise ValueError('Pedestrian microphone source missing')
        if row['rider_device_class'] not in ('bicycle', 'electric_bicycle', 'electric_scooter'):
            raise ValueError('Covered device class source missing')
        for key in ('rider_footprint_xy_m', 'pedestrian_footprint_xy_m'):
            if len(row[key]) != 4:
                raise ValueError('Full participant footprint source missing')
            if any(not (-20 <= x <= 50 and -1.5 <= y <= 1.5) for x, y in row[key]):
                raise ValueError('Participant footprint departed source sidewalk')
    return rows


def x_interval(points):
    xs = [point[0] for point in points]
    return min(xs), max(xs)


def measure(path):
    rows = read_rows(path)
    behind, ahead, audio, pauses, gaps = [], [], [], [], []
    for i, row in enumerate(rows):
        rlo, rhi = x_interval(row['rider_footprint_xy_m'])
        plo, phi = x_interval(row['pedestrian_footprint_xy_m'])
        if rhi < plo:
            behind.append(i)
        if rlo > phi:
            ahead.append(i)
        if rhi >= plo and rlo <= phi:
            # The lateral separation is measured from the two full footprints.
            ry = max(p[1] for p in row['rider_footprint_xy_m'])
            py = min(p[1] for p in row['pedestrian_footprint_xy_m'])
            gaps.append({'frame': i, 'surface_gap_m': py - ry})
        if row['rider_speed_mps'] <= 0.05:
            pauses.append(i)
        samples = row['microphone_at_pedestrian_pcm']
        rms = math.sqrt(sum((sample - 0.2)**2 for sample in samples) / len(samples))
        if rms >= 0.6:  # Diagnostic detector threshold, not an audibility rule.
            audio.append(i)
    pass_start = next((i for i in range(FRAMES) if i not in behind), None)
    pass_end = next((i for i in ahead if pass_start is not None and i > pass_start), None)
    signal_onset = audio[0] if audio else None
    return {'format': 'sidewalk-pedestrian-source-diagnostic-v1',
            'source_path': str(path), 'source_sha256': sha(path), 'frames': FRAMES,
            'rate_hz': HZ, 'duration_s': FRAMES/HZ,
            'source_kind': 'synthetic_local_diagnostic',
            'rider_device_class': rows[0]['rider_device_class'],
            'participant_ids': [rows[0]['rider_id'], rows[0]['pedestrian_id']],
            'sidewalk_footprints_recorded': True,
            'first_overlap_frame': pass_start, 'first_fully_ahead_frame': pass_end,
            'first_pedestrian_microphone_pulse_frame': signal_onset,
            'pulse_before_first_overlap': signal_onset is not None and pass_start is not None and signal_onset < pass_start,
            'requested_pause_frames': [pauses[0], pauses[-1]] if pauses else [],
            'minimum_lateral_surface_gap_m': min((v['surface_gap_m'] for v in gaps), default=None),
            'microphone_threshold_relative_amplitude': 0.6,
            'audio_legal_audibility_proven': False, 'right_of_way_legal_verdict': None,
            'municipal_applicability_verified': False, 'native_motion_verified': False}


def prove(output):
    output.mkdir(parents=True, exist_ok=True)
    variants = {'signal_before_pass': (80, True),
                'signal_after_pass': (400, True),
                'no_signal': (None, True),
                'no_yield_pause': (80, False)}
    reports = {}
    for name, (signal, pause) in variants.items():
        path = output / (name + '.jsonl')
        write_rows(path, signal, pause)
        reports[name] = measure(path)
    assert reports['signal_before_pass']['pulse_before_first_overlap']
    assert not reports['signal_after_pass']['pulse_before_first_overlap']
    assert not reports['no_signal']['pulse_before_first_overlap']
    assert reports['signal_before_pass']['requested_pause_frames']
    assert not reports['no_yield_pause']['requested_pause_frames']
    damaged = output / 'missing_audio.jsonl'
    data = (output / 'signal_before_pass.jsonl').read_text().splitlines()
    row = json.loads(data[3]); del row['microphone_at_pedestrian_pcm']
    data[3] = json.dumps(row, separators=(',', ':'))
    damaged.write_text('\n'.join(data) + '\n')
    try:
        measure(damaged)
    except KeyError:
        missing_audio_rejected = True
    else:
        missing_audio_rejected = False
    assert missing_audio_rejected
    return {'format': 'sidewalk-pedestrian-meter-proof-v1', 'passed': True,
            'variants': reports, 'missing_audio_rejected': True,
            'scope': 'CPU source-shaped diagnostic; no Native/audio/legal/physical acceptance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.output), indent=2, allow_nan=False))
