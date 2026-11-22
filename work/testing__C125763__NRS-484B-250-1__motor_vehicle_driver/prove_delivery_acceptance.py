"""CPU diagnostics for the prospective independent Native delivery audit."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_audit import CASE_IDS, CHECKS, audit_sources, pixel_checker, verify_physical  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.media import Frame  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    if args.case not in CASE_IDS or len(CHECKS) != 6:
        raise ValueError('Exact delivery audit case/check inventory differs')
    entry = next(e for e in json.loads((HERE / 'execution-manifest.json').read_text())['cases']
                 if e['case_id'] == args.case)
    construction = HERE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction source changed')
    config = json.loads(next(f['content'] for f in json.loads(construction.read_text())['files']
                             if f['path'] == 'config.json'))
    criterion = config['physical_completion']
    if (criterion['criterion'] != 'intersection_clearance' or
            criterion['body_key'] != 'ego.body_vertices_xy_m' or
            criterion['motion_source'] != 'crossing_history.jsonl' or
            config['frames'] != 900 or config['rate_hz'] != 20):
        raise ValueError('Exact physical or duration criterion differs')
    post = entry['post_capture']
    saved_log = HERE / post['test_log']
    if (post.get('test_exit_code') != 0 or not post.get('recorded_only') or
            sha(saved_log) != post['test_log_sha256'] or
            args.case not in saved_log.read_text() or
            '"recorded_only": true' not in saved_log.read_text()):
        raise ValueError('Current full saved-only decode proof changed')
    attempt = REPO / entry['post_capture']['command'].split('--attempt ', 1)[1].split(' --output ', 1)[0]
    if not attempt.is_dir():
        raise ValueError('Current saved-source diagnostic attempt missing')
    with tempfile.TemporaryDirectory(prefix='c125763-acceptance-') as temporary:
        root = Path(temporary)
        for name in ('video_frames.jsonl', 'crossing_history.jsonl',
                     'controller_history.jsonl', 'trace.jsonl'):
            (root / name).symlink_to((attempt / name).resolve())
        (root / 'result.json').write_text(json.dumps({'case_id': args.case}) + '\n')
        sources = audit_sources(root, args.case)
        if sources != {'original_frame_count': 900, 'time_join': True,
                       'all_participants': True}:
            raise AssertionError('Full original source join differs')
        check = {'status': 'met', 'method': 'synthetic source-bound completion boundary',
                 'sources': {'crossing_history.jsonl': sha(root / 'crossing_history.jsonl')}}
        physical = {'physical_acceptance_claimed': False,
                    'setup_confirmed': True, 'behavior_attempted': True,
                    'maneuver_completed': True,
                    'physical_checks': {name: check for name in ('setup', 'target', 'maneuver')}}
        # The source below is copied into the attempt so the production path check
        # can distinguish a changed original from a stale expected digest.
        (root / 'physical-source.jsonl').write_text('{"diagnostic":true}\n')
        check['sources'] = {'physical-source.jsonl': sha(root / 'physical-source.jsonl')}
        verify_physical(physical, root)
        sample = [{'video_frame': 0, 'actor_id': 17, 'bbox_xyxy': [0, 0, 4, 4]}]
        callback, finish = pixel_checker(sample, 4, 4)
        pixels = bytearray(b'\0\0\0' * 16)
        try:
            callback(Frame(0, 4, 4, bytes(pixels)))
        except ValueError as error:
            if 'no visible pixel detail' not in str(error):
                raise
        else:
            raise AssertionError('Blank actor pixels passed independent review')
        pixels[:3] = b'\xff\0\0'
        callback(Frame(0, 4, 4, bytes(pixels)))
        finish()
        if args.mode == 'negative':
            (root / 'physical-source.jsonl').write_text('{"tampered":true}\n')
            verify_physical(physical, root)
            raise AssertionError('Tampered physical source passed')
    print(json.dumps({'case_id': args.case, 'mode': args.mode,
                      'checks': CHECKS, 'original_frame_count': 900,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
