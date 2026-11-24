"""Independent diagnostic source/decode audit for one exact C125714 case."""
import argparse
import json
import sys
from pathlib import Path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    sys.path[:0] = [str(folder), 'runtime']
    from delivery_audit import sha, verify_frame_join, verify_saved_join, audit_sources
    from pixel_checks import pixel_presence
    from scenario_pipeline.worker_exchange.media import audit

    case = args.case_id.split('__')[-1]
    source = args.scratch / ('source-' + case)
    saved = args.scratch / ('saved-' + case) / 'v0001'
    frame_map = rows(source / 'video_frames.jsonl')
    trace = rows(source / 'trace.jsonl')
    ego = rows(source / 'ego-body-history.jsonl')
    other = rows(source / 'other-body-history.jsonl')
    controller_path = source / 'controller-history.jsonl'
    controller = rows(controller_path) if controller_path.is_file() else None
    site = json.loads((source / 'site-context.json').read_text())
    if args.negative:
        ego.pop()
        # This intentionally exits nonzero with the original-source error.
        verify_frame_join(frame_map, trace, ego, other, site, len(frame_map), controller)
        raise AssertionError('missing original ego body sample was accepted')
    count = verify_frame_join(frame_map, trace, ego, other, site, len(frame_map), controller)
    source_names = ('video_frames.jsonl', 'trace.jsonl', 'ego-body-history.jsonl',
                    'other-body-history.jsonl',
                    'road.xodr', 'site-context.json', 'overview.mkv', 'approach.mkv',
                    'reference_corner.mkv', 'driver_reference.mkv')
    native = {'frames': count, 'sources': {name: sha(source / name) for name in source_names}}
    if controller_path.is_file():
        native['sources'][controller_path.name] = sha(controller_path)
    processing = json.loads((saved / 'processing.json').read_text())
    verify_saved_join(processing, native, args.case_id)
    assert processing['result_sha256'] == sha(saved / 'analysis/result.json')
    assert processing['final_video_checks']['video_sha256'] == sha(saved / 'analysis/event_review.webm')
    assert (saved / 'analysis/traffic_spec/trace.json').is_file()
    diagnostic_rejected = False
    try:
        audit_sources(source, args.case_id)
    except (ValueError, FileNotFoundError):
        diagnostic_rejected = True
    assert diagnostic_rejected, 'diagnostic source was accepted as Native'
    check_path = folder / 'pixel_checks.py'
    receipt = args.scratch / ('pixel-decode-' + case + '.json')
    decoded = audit(saved / 'analysis/event_review.webm', count,
                    checkers={'pixel_presence': (sha(check_path), pixel_presence)},
                    mapping_sha256=sha(source / 'video_frames.jsonl'), receipt=receipt)
    assert decoded['passed'] and decoded['checks']['pixel_presence'] == sha(check_path)
    physical = json.loads((folder / 'cases' / case / 'physical-complete_motion.json').read_text())
    assert physical['physical_checks']['maneuver']['status'] == 'met'
    assert physical['diagnostic_fixture'] is True
    print(json.dumps({'case_id': args.case_id, 'frames': count,
                      'checks': ['native_source', 'all_participants', 'time_join',
                                 'full_video_decode', 'actual_pixels', 'physical_completion'],
                      'diagnostic_source_rejected_by_delivery': True,
                      'controller_history_present': controller is not None,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
