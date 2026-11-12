"""Independently audit exact Native indicator activation-index diagnostics."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from turn_signal_measurement import measure

SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]

def audit(activation, attempt, baseline, *, negative=False):
    case = HERE.name + f'__indicator_activation_{activation}f'
    root, other = Path(attempt), Path(baseline)
    report = json.loads((root / 'analysis-report.json').read_text())
    if (report.get('case_id') != case or report.get('physical_acceptance_claimed')
            or report.get('legal_acceptance_claimed')):
        raise ValueError('Wrong or overclaimed indicator timing report')
    measured = report['measurements']['turn_signal_observation']
    hashes = {name: sha(root / name) for name in
              (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    if negative:
        measured['sources']['ego_signal_audio.jsonl'] = '0' * 64
    if measured.get('sources') != hashes:
        raise ValueError('Stale or missing original indicator timing source')
    observation = measure(*(root / name for name in SOURCES))
    baseline_observation = measure(*(other / name for name in SOURCES))
    if observation != measured['value'] or baseline_observation['pre_turn_indicator_frames']:
        raise ValueError('Original indicator timing report differs')
    if (observation['pedestrian_may_be_affected'] or
            not observation['vehicle_may_be_affected'] or
            observation['reasonable_safety_legal_judgment'] is not None):
        raise ValueError('Affected context or legal judgment differs')
    fixed = ('ego_turn_motion.jsonl', 'affected_participants.json',
             'participant_bodies.jsonl', 'trace.jsonl', 'video_frames.jsonl', *VIDEOS)
    for name in fixed:
        if sha(root / name) != sha(other / name):
            raise ValueError('Fixed original indicator timing source differs: ' + name)
    signal = rows(root / 'ego_signal_audio.jsonl')
    base_signal = rows(other / 'ego_signal_audio.jsonl')
    if len(signal) != len(base_signal):
        raise ValueError('Original signal frame count differs')
    for index, (item, control) in enumerate(zip(signal, base_signal)):
        if (item.get('indicator_readback') != ('left' if index >= activation else 'off')
                or control.get('indicator_readback') != 'off'):
            raise ValueError('Exact original activation index differs')
        item = dict(item); control = dict(control)
        item.pop('indicator_readback'); control.pop('indicator_readback')
        if item != control:
            raise ValueError('Another original signal field changed')
    expected_preturn = max(0, 6 - activation)
    if len(observation['pre_turn_indicator_frames']) != expected_preturn:
        raise ValueError('Diagnostic preturn readback count differs')
    mapping, trace = rows(root / 'video_frames.jsonl'), rows(root / 'trace.jsonl')
    if len(mapping) != len(trace) or len(mapping) != observation['frame_count']:
        raise ValueError('Original video/trace coverage differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if (mapped.get('video_frame') != index or
                (mapped.get('carla_frame'), mapped.get('time_s')) !=
                (point.get('frame'), point.get('time_s'))):
            raise ValueError('Original video/trace join differs')
    for name in VIDEOS:
        audit_video(root / name, len(mapping), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-indicator-activation-audit', 'case_id': case,
            'activation_frame_index': activation,
            'diagnostic_pre_turn_indicator_frames': expected_preturn,
            'source_integrity_passed': True, 'controlled_pair_passed': True,
            'video_decode_count': 4, 'joined_frames': len(mapping),
            'native_pre_turn_timing_verified': False,
            'physical_visibility_verified': False,
            'legal_acceptance_claimed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--activation', type=int, choices=(2, 4, 6), required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.case != HERE.name + f'__indicator_activation_{args.activation}f':
        raise ValueError('Wrong exact indicator activation case')
    receipt = audit(args.activation, args.attempt, args.baseline,
                    negative=args.negative)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print('indicator_activation_source_audit_passed', args.activation)
