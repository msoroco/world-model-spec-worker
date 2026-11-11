"""Independent first-case source and full-video delivery audit."""
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

CASE = ROOT.name + '__vehicle_left_indicator'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, report, *, receipt_dir=None):
    root = Path(attempt)
    if report.get('case_id') != CASE or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong or overclaimed indicator delivery report')
    measurement = report['measurements']['turn_signal_observation']
    required = {name: sha(root / name) for name in (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    if measurement.get('sources') != required:
        raise ValueError('Stale or missing original indicator source')
    recomputed = measure(*(root / name for name in SOURCES))
    if recomputed != measurement.get('value'):
        raise ValueError('Indicator report differs from original-source recomputation')
    if (recomputed['pedestrian_may_be_affected'] is not False or
            recomputed['vehicle_may_be_affected'] is not True or
            recomputed['max_pre_turn_listener_audio_rms'] is not None or
            not recomputed['pre_turn_indicator_frames'] or
            recomputed['appropriate_signal_legal_judgment'] is not None):
        raise ValueError('Indicator context or unresolved judgment differs')
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    if len(mapping) != len(trace) or len(mapping) != recomputed['frame_count']:
        raise ValueError('Original video/trace/indicator frame count differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if (mapped.get('video_frame') != index or
                (mapped.get('carla_frame'), mapped.get('time_s')) !=
                (point.get('frame'), point.get('time_s'))):
            raise ValueError('Original indicator video/trace join differs')
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
    decodes = {}
    for name in VIDEOS:
        receipt = None if receipt_dir is None else receipt_dir / (name[:-4] + '-decode.json')
        decodes[name] = audit_video(root / name, len(mapping), mapping_sha256=required['video_frames.jsonl'],
                                    receipt=receipt)
    return {'format': 'worker-vehicle-indicator-source-audit', 'case_id': CASE,
            'source_integrity_passed': True, 'original_sha256': required,
            'video_decode_count': len(decodes), 'joined_frames': len(mapping),
            'indicator_before_turn_frames': recomputed['pre_turn_indicator_frames'],
            'pedestrian_audio_not_required': True,
            'physical_visibility_verified': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.case != CASE:
        raise ValueError('Wrong exact indicator audit case')
    root = Path(args.attempt)
    report = json.loads((root / 'analysis-report.json').read_text())
    if args.negative:
        report['measurements']['turn_signal_observation']['sources']['ego_signal_audio.jsonl'] = '0' * 64
    receipt = audit(root, report, receipt_dir=None if args.negative else Path(args.output).parent / 'video-decodes')
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'source_integrity_passed': True,
                      'joined_frames': receipt['joined_frames'],
                      'physical_visibility_verified': False}))


if __name__ == '__main__':
    main()
