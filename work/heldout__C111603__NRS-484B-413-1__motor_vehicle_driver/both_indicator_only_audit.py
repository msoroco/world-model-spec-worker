"""Independent affected-pedestrian listener-source and video audit."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from turn_signal_measurement import measure

CASE = ROOT.name + '__both_indicator_only'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl',
           'listener_audio_original.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt, *, negative=False):
    root = Path(attempt)
    report = json.loads((root / 'analysis-report.json').read_text())
    if report.get('case_id') != CASE or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong or overclaimed affected-pedestrian report')
    item = report['measurements']['turn_signal_observation']
    hashes = {name: sha(root / name) for name in (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    if negative:
        item['sources']['listener_audio_original.jsonl'] = '0' * 64
    if item.get('sources') != hashes:
        raise ValueError('Stale or missing original pedestrian listener source')
    value = measure(*(root / name for name in SOURCES[:4]))
    if value != item['value'] or not value['pedestrian_may_be_affected'] or not value['vehicle_may_be_affected']:
        raise ValueError('Affected-pedestrian measurement or context differs')
    if value['clearly_audible_legal_judgment'] is not None or value['max_pre_turn_listener_audio_rms'] is None or not value['pre_turn_indicator_frames']:
        raise ValueError('Original listener observation or unresolved judgment differs')
    signals, packets = rows(root / 'ego_signal_audio.jsonl'), rows(root / 'listener_audio_original.jsonl')
    if len(signals) != len(packets) or len(signals) != value['frame_count']:
        raise ValueError('Original listener packet inventory differs')
    for signal, packet in zip(signals, packets):
        samples = packet.get('samples')
        if (packet.get('origin') != 'listener_pcm_capture' or
                not packet.get('capture_source') or not packet.get('capture_source_sha256') or
                not packet.get('capture_provenance') or
                packet.get('frame') != signal.get('frame') or
                packet.get('listener_id') != signal.get('listener_id') or
                samples != signal.get('listener_audio_samples') or
                signal.get('listener_audio_status') != 'original_pcm'):
            raise ValueError('Original listener PCM packet differs from measurement row')
        digest = sha256(json.dumps(samples, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if packet.get('sha256') != digest or signal.get('listener_packet_sha256') != digest:
            raise ValueError('Original listener PCM sample hash differs')
    mapping, trace = rows(root / 'video_frames.jsonl'), rows(root / 'trace.jsonl')
    if len(mapping) != len(trace) or len(mapping) != value['frame_count']:
        raise ValueError('Original pedestrian video/trace frame count differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if mapped.get('video_frame') != index or \
           (mapped.get('carla_frame'), mapped.get('time_s')) != (point.get('frame'), point.get('time_s')):
            raise ValueError('Original pedestrian video/trace join differs')
    for name in VIDEOS:
        audit_video(root / name, len(mapping), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-pedestrian-listener-source-audit', 'case_id': CASE,
            'source_integrity_passed': True, 'listener_packets_joined': len(packets),
            'video_decode_count': 4, 'joined_frames': len(mapping),
            'diagnostic_pre_turn_listener_rms': value['max_pre_turn_listener_audio_rms'],
            'physical_audibility_verified': False, 'legal_acceptance_claimed': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    if args.case != CASE:
        raise ValueError('Wrong exact pedestrian audit case')
    receipt = audit(args.attempt, negative=args.negative)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'source_integrity_passed': True,
                      'listener_packets_joined': receipt['listener_packets_joined']}))


if __name__ == '__main__':
    main()
