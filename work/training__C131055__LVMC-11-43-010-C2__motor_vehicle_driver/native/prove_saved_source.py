"""Exercise exact saved-source joins on synthetic fixtures only."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finalize import analyze


def reject(call, expected):
    try:
        call()
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return
    raise AssertionError('Expected rejection: ' + expected)


def probe(path, lane):
    path = Path(path)
    result = analyze(path)['measurement']
    assert result['exit_intent'] == 'right_turn'
    assert result['frame_count'] == 600
    assert result[lane + '_lane_frame_count'] == result['circulation_frame_count']
    assert result['lane_change_count'] == 0
    assert 1.35 < result['angular_sweep_rad'] < 1.75
    assert result['legal_compliance'] == 'unassessed'
    name = path / 'roundabout-map-readback.json'
    saved = name.read_bytes()
    name.unlink()
    try:
        reject(lambda: analyze(path), 'Missing required source: roundabout-map-readback.json')
    finally:
        name.write_bytes(saved)
    name = path / 'native-raw-actors.jsonl'
    saved = name.read_bytes()
    rows = [json.loads(s) for s in saved.splitlines()]
    rows[100]['actors'][0]['road_id'] = 99
    name.write_text('\n'.join(json.dumps(row, separators=(',', ':')) for row in rows) + '\n')
    try:
        reject(lambda: analyze(path), 'Original subject roadway phase unobserved')
    finally:
        name.write_bytes(saved)
    name = path / 'control-intent.jsonl'
    saved = name.read_bytes()
    rows = [json.loads(s) for s in saved.splitlines()]
    rows[100]['exit_intent'] = 'left_turn'
    name.write_text('\n'.join(json.dumps(row, separators=(',', ':')) for row in rows) + '\n')
    try:
        reject(lambda: analyze(path), 'Original control intent differs')
    finally:
        name.write_bytes(saved)
    assert analyze(path)['measurement'][lane + '_lane_frame_count'] == result['circulation_frame_count']
    return {'lane': lane, 'circulation_frames': result['circulation_frame_count'],
            'negative_rejections': 3}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--right-fixture', required=True)
    parser.add_argument('--left-fixture', required=True)
    args = parser.parse_args()
    print(json.dumps({'synthetic_only': True,
                      'probes': [probe(args.right_fixture, 'right'),
                                 probe(args.left_fixture, 'left')]}, sort_keys=True))
