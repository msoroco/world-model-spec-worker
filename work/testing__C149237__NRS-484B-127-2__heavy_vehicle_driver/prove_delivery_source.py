"""Positive and negative CPU proofs for the independent truck-source join."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from delivery_audit import source_join, require_native_delivery


FILES = ('config.json', 'road_context.json', 'truck_history.jsonl', 'capture/evidence.jsonl',
         'video_frames.jsonl', 'trace.jsonl', 'fixture-provenance.json', 'result.json')


def rejected(fn, expected):
    try:
        fn()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Expected {expected!r}; got {error!r}') from error
        return str(error)
    raise AssertionError('Negative source audit unexpectedly passed: ' + expected)


def rewrite_first(path, change):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    change(rows[0])
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    with tempfile.TemporaryDirectory(prefix='c149237-delivery-source-') as temp:
        root = Path(temp)
        for name in FILES:
            original = source/name
            if original.is_file():
                (root/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(original, root/name)
        positive = source_join(root, args.case, expected_frames=9)
        assert positive['frames'] == 9 and len(positive['participant_ids']) == 2
        negatives = {}
        negatives['full_duration'] = rejected(
            lambda: source_join(root, args.case, expected_frames=900),
            'Original source frame count differs from planned capture')
        negatives['diagnostic_delivery'] = rejected(
            lambda: require_native_delivery(root, args.case, 'fixture-job', 1,
                                            'fixture-recording', root/'review.json',
                                            root/'delivery-audit.json',root.parent/'decode.json'),
            'Original source frame count differs from planned capture')
        path = root/'truck_history.jsonl'
        original = path.read_bytes()
        rewrite_first(path, lambda row: row['ego'].__setitem__('body_vertices_xy_m', []))
        negatives['missing_body'] = rejected(
            lambda: source_join(root, args.case, expected_frames=9),
            'Missing complete truck body')
        path.write_bytes(original)
        rewrite_first(path, lambda row: row['lead'].__setitem__('actor_id', row['ego']['actor_id']))
        negatives['duplicate_actor'] = rejected(
            lambda: source_join(root, args.case, expected_frames=9),
            'Truck roles share one actor identity')
        path.write_bytes(original)
        path = root/'video_frames.jsonl'
        original = path.read_bytes()
        rewrite_first(path, lambda row: row.__setitem__('video_frame', 8))
        negatives['frame_join'] = rejected(
            lambda: source_join(root, args.case, expected_frames=9),
            'Original frame/time join differs')
        path.write_bytes(original)
        path = root/'capture/evidence.jsonl'
        original = path.read_bytes()
        rewrite_first(path, lambda row: row['original_observations'].__setitem__('participants', []))
        negatives['missing_participants'] = rejected(
            lambda: source_join(root, args.case, expected_frames=9),
            'Missing complete participant inventory')
        path.write_bytes(original)
        (root/'truck_history.jsonl').unlink()
        negatives['missing_history'] = rejected(
            lambda: source_join(root, args.case, expected_frames=9),
            'Missing original source: truck_history.jsonl')
    print(json.dumps({'format':'worker-truck-source-audit-cpu-proof',
                      'passed':True,'source_join':positive,'negative_rejections':negatives},
                     sort_keys=True))


if __name__ == '__main__':
    main()
