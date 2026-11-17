"""Prepare a fresh synthetic signed-bus Native attempt with four camera files."""
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

MANIFESTS = {
    'shuttle_bus': ROOT / 'execution-manifest-diagnostic-shuttle_bus_below-draft.json',
    'rtc_bus': ROOT / 'execution-manifest-diagnostic-rtc_bus_below-draft.json',
    'limo': ROOT / 'execution-manifest-diagnostic-limo_below-draft.json',
}
SPEC = importlib.util.spec_from_file_location('bus_source_helpers',
                                            ROOT / 'prove-tour-bus-saved-source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def prepare(case, candidate, attempt, media_from, manifest_override=None):
    service = case.rsplit('_', 1)[0] if not case.endswith('no_loading') else case[:-len('_no_loading')]
    if service not in MANIFESTS or case not in tuple(
            name + '_' + boundary for name in MANIFESTS
            for boundary in ('below', 'at', 'above', 'no_loading')):
        raise ValueError('Unknown signed-bus case')
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown shuttle candidate')
    attempt = Path(attempt).resolve()
    media_from = Path(media_from).resolve()
    if REPO / '.runtime-work' not in attempt.parents or \
       REPO / '.runtime-work' not in media_from.parents:
        raise ValueError('Diagnostic acquisition and media belong under .runtime-work')
    if attempt.exists():
        raise ValueError('Use a fresh acquisition directory')
    manifest = Path(manifest_override).resolve() if manifest_override else MANIFESTS[service]
    if manifest_override and (service != 'limo' or manifest != ROOT / 'execution-manifest-diagnostic-limo_below-draft-v2.json'):
        raise ValueError('Only the corrected limousine draft manifest is supported')
    materialize(manifest, ROOT.name + '__' + case, attempt, candidate)
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
    parser.add_argument('--manifest')
    args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.candidate, args.attempt,
                             args.media_from, args.manifest), sort_keys=True))
