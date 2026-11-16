"""Prepare a fresh synthetic shuttle Native attempt with four actual camera files."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize

MANIFEST = ROOT / 'execution-manifest-diagnostic-shuttle_bus_below-draft.json'
SPEC = importlib.util.spec_from_file_location('bus_source_helpers',
                                            ROOT / 'prove-tour-bus-saved-source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def prepare(case, candidate, attempt, media_from):
    if case not in ('shuttle_bus_below', 'shuttle_bus_at', 'shuttle_bus_above',
                    'shuttle_bus_no_loading'):
        raise ValueError('Unknown shuttle case')
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown shuttle candidate')
    attempt = Path(attempt).resolve()
    media_from = Path(media_from).resolve()
    if REPO / '.runtime-work' not in attempt.parents or \
       REPO / '.runtime-work' not in media_from.parents:
        raise ValueError('Diagnostic acquisition and media belong under .runtime-work')
    if attempt.exists():
        raise ValueError('Use a fresh acquisition directory')
    materialize(MANIFEST, ROOT.name + '__' + case, attempt, candidate)
    SOURCE.source_rows(attempt)
    expected = json.loads((attempt / 'config.json').read_text())['capture_frames']
    actual = json.loads((media_from / 'config.json').read_text())['capture_frames']
    if expected != actual:
        raise ValueError('Reusable camera media has a different exact frame count')
    for view in VIEWS:
        source = media_from / (view + '.mkv')
        if not source.is_file():
            raise ValueError('Missing reusable camera source: ' + view)
        shutil.copy2(source, attempt / source.name)
    return {'case_id': ROOT.name + '__' + case, 'candidate': candidate,
            'capture_frames': expected, 'four_source_cameras': list(VIEWS),
            'source_kind': 'synthetic_native_sample',
            'media_reused_from': str(media_from), 'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--media-from', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.candidate, args.attempt,
                             args.media_from), sort_keys=True))
