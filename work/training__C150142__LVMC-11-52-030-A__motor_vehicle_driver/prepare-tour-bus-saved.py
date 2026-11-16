"""Materialize one source-bound, synthetic long tour-bus saved-processing attempt.

Media and acquisition rows remain under ignored .runtime-work; returned work holds
only this reproducible preparation code and later small text receipts.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PIPELINE = REPO / 'runtime/pipeline/scenario_pipeline'
sys.path.insert(0, str(PIPELINE))
from worker_exchange.runtime_cli import materialize

MANIFEST = ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json'
PILOT = REPO / '.runtime-work/c150142-long-media-pilot/overview-36120-lossless.mkv'


def prepare(attempt, *, case='tour_bus_below', reuse_media_from=None):
    attempt = Path(attempt).resolve()
    if REPO / '.runtime-work' not in attempt.parents:
        raise ValueError('Diagnostic acquisition belongs under .runtime-work')
    if attempt.exists():
        raise ValueError('Use a fresh synthetic acquisition directory')
    if case not in ('tour_bus_below', 'tour_bus_at', 'tour_bus_above'):
        raise ValueError('Unsupported source-bound loading case')
    case_id = ROOT.name + '__' + case
    materialize(MANIFEST, case_id, attempt, 'primary')
    module = importlib.util.spec_from_file_location(
        'tour_bus_source_proof', ROOT / 'prove-tour-bus-saved-source.py')
    source = importlib.util.module_from_spec(module)
    module.loader.exec_module(source)
    source.source_rows(attempt)
    frames = json.loads((attempt / 'config.json').read_text())['capture_frames']
    if reuse_media_from is not None:
        reuse_media_from = Path(reuse_media_from).resolve()
        if REPO / '.runtime-work' not in reuse_media_from.parents:
            raise ValueError('Reusable synthetic media belongs under .runtime-work')
    if reuse_media_from is not None:
        shutil.copy2(reuse_media_from / 'overview.mkv', attempt / 'overview.mkv')
    elif case == 'tour_bus_below' and PILOT.is_file():
        shutil.copy2(PILOT, attempt / 'overview.mkv')
    for view, color, size in (('overview', 'black', '1920x1080'),
                        ('approach', 'red', '1280x720'),
                        ('reference_corner', 'green', '1280x720'),
                        ('driver_reference', 'blue', '1280x720')):
        output = attempt / (view + '.mkv')
        if view == 'overview' and (reuse_media_from is not None or
                                   case == 'tour_bus_below' and PILOT.is_file()):
            continue
        output.unlink(missing_ok=True)
        if reuse_media_from is not None:
            shutil.copy2(reuse_media_from / (view + '.mkv'), output)
            continue
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                   '-f', 'lavfi', '-i', 'color=c=' + color + ':s=' + size + ':r=20',
                   '-frames:v', str(frames), '-an', '-c:v', 'libx265',
                   '-preset', 'ultrafast', '-x265-params',
                   'lossless=1:log-level=error', '-threads', '2', str(output)]
        subprocess.run(command, check=True, timeout=1800)
    return {'case_id': case_id, 'attempt': str(attempt),
            'source_kind': 'synthetic_native_sample', 'camera_sources':
            ['overview.mkv', 'approach.mkv', 'reference_corner.mkv',
             'driver_reference.mkv'], 'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', default='tour_bus_below')
    parser.add_argument('--reuse-media-from')
    args = parser.parse_args()
    print(json.dumps(prepare(args.attempt, case=args.case,
                             reuse_media_from=args.reuse_media_from), sort_keys=True))
