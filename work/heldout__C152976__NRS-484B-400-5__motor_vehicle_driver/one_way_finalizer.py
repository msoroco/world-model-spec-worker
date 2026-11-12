"""Saved-only original-source measurements for the one-way left-turn cases.

This module consumes retained Native rows. It does not infer a legal cutoff for
"as close as practicable" or take the requested construction as observed fact.
"""
import argparse
import hashlib
import json
from pathlib import Path

from one_way_left import measure


REQUIRED = ('video_frames.jsonl', 'native/footprints.jsonl', 'native/road_edges.jsonl')


def _rows(path):
    if not path.is_file():
        raise ValueError('missing original source: ' + str(path))
    data = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not data:
        raise ValueError('empty original source: ' + str(path))
    return data


def _key(row):
    try:
        if type(row['video_frame']) is not int or type(row['native_frame']) is not int:
            raise ValueError('original frame identity type invalid')
        if row.get('carla_frame') != row['native_frame']:
            raise ValueError('CARLA/native original identity differs')
        return (row['video_frame'], row['native_frame'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('original frame identity missing') from exc


def _index(rows, label):
    out = {}
    for row in rows:
        key = _key(row)
        if key in out:
            raise ValueError('duplicate ' + label + ' frame')
        out[key] = row
    return out


def finalize(source_dir):
    root = Path(source_dir)
    sources = {name: root / name for name in REQUIRED}
    frame_rows = _rows(sources['video_frames.jsonl'])
    bodies = _index(_rows(sources['native/footprints.jsonl']), 'footprint')
    edges = _index(_rows(sources['native/road_edges.jsonl']), 'road edge')
    frames = _index(frame_rows, 'frame map')
    if set(frames) != set(bodies) or set(frames) != set(edges):
        raise ValueError('original frame/source join incomplete')
    if [key[0] for key in sorted(frames)] != list(range(len(frames))):
        raise ValueError('original video frame sequence incomplete')
    observed = []
    prior_time = None
    for key in sorted(frames):
        frame, body, edge = frames[key], bodies[key], edges[key]
        t = frame.get('time_s')
        if not isinstance(t, (int, float)) or (prior_time is not None and t <= prior_time):
            raise ValueError('nonmonotonic original time')
        prior_time = t
        if body.get('actor_id') != frame.get('subject_actor_id'):
            raise ValueError('subject actor identity differs')
        if body.get('road_id') != edge.get('road_id'):
            raise ValueError('original road identity differs')
        if not edge.get('one_way_source') or not edge.get('curb_source'):
            raise ValueError('original one-way or curb source absent')
        if edge.get('native_road_direction') not in ('north', 'west'):
            raise ValueError('unverified one-way direction')
        observed.append({
            'time_s': t,
            'native_road_direction': edge['native_road_direction'],
            'body_corners_xy': body.get('body_corners_xy'),
            'observed_left_curb_x': edge.get('observed_left_curb_x'),
            'observed_left_curb_y': edge.get('observed_left_curb_y'),
            'source': 'native/footprints.jsonl + native/road_edges.jsonl',
        })
    result = measure(observed)
    result['original_frame_count'] = len(frames)
    result['source_sha256'] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for name, path in sources.items()}
    result['source_kind'] = 'retained_original_native'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(args.source_dir)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
