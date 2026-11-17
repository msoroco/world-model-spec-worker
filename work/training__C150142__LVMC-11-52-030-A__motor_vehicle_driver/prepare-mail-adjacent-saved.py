"""Materialize a synthetic four-camera mail-adjacent Native diagnostic."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


SOURCE = module('emergency_source', 'prove-mail-adjacent-source.py')
GRAPH = module('emergency_graph', 'build-mail-adjacent-native-diagnostic.py')


def prepare(candidate, attempt, media_from):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown mail-adjacent candidate')
    attempt, media_from = Path(attempt).resolve(), Path(media_from).resolve()
    private = REPO / '.runtime-work'
    if private not in attempt.parents or private not in media_from.parents or \
            attempt.exists():
        raise ValueError('Use a fresh ignored diagnostic directory')
    SOURCE.materialize(SOURCE.MANIFEST, SOURCE.CASE, attempt, candidate)
    SOURCE.source_rows(attempt)
    graph = GRAPH.build(attempt)
    if json.loads((attempt / 'config.json').read_text())['capture_frames'] != 361:
        raise ValueError('Emergency-business frame count differs')
    for view in VIEWS:
        source = media_from / (view + '.mkv')
        if not source.is_file():
            raise ValueError('Missing decoded-camera source: ' + view)
        shutil.copy2(source, attempt / source.name)
    return {'candidate': candidate, 'case_id': SOURCE.CASE,
            'source_kind': 'synthetic_native_sample', 'graph': graph,
            'four_source_cameras': list(VIEWS), 'media_reused_from': str(media_from),
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--media-from', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.candidate, args.attempt, args.media_from),
                     sort_keys=True))
