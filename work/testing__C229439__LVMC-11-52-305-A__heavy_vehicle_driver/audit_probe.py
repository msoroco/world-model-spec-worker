"""Build explicit synthetic audit fixtures and exercise source mutation rejection."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from delivery_audit import CAMERAS, SOURCES, audit, sha


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    suffix = args.case.rsplit('__', 1)[-1]
    if args.case != ROOT.name + '__' + suffix:
        raise ValueError('exact service parking assignment mismatch')
    pipeline_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not pipeline_root.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    source = REPO / '.runtime-work/lvmc305-saved-v1' / (suffix + '-attempt')
    saved = REPO / '.runtime-work/lvmc305-saved-v1' / (suffix + '-output/v0001/processing.json')
    output = Path(args.output).resolve()
    if not output.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('CPU audit scratch belongs under .runtime-work')
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    result = json.loads((output / 'result.json').read_text())
    result['physical_checks']['maneuver']['status'] = 'met'
    result['maneuver_completed'] = True
    write(output / 'result.json', result)
    write(output / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    needed = list(SOURCES) + [name + '.mkv' for name in CAMERAS]
    seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'frames': 9,
            'restoration': {'restored': True},
            'sources': {name: sha(output / name) for name in needed},
            'native_revision': {'construction_sha256': sha(output / 'construction.json'),
                                'runner_sha256': sha(output / 'runner.py')},
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified']}
    write(output / 'capture-seal.json', seal)
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    record_native_exit(output)
    acknowledge_owner_release(output, output / 'owner-release.json', True)
    source_raw = saved.parent / 'analysis/raw.mkv'
    raw_dir = output / 'cpu-saved-video'
    raw_dir.mkdir()
    shutil.copy2(source_raw, raw_dir / 'raw.mkv')
    receipt = json.loads(saved.read_text())
    receipt['result'] = str(output / 'result.json')
    receipt['result_sha256'] = sha(output / 'result.json')
    receipt['analysis_directory'] = str(raw_dir)
    processing = output / 'cpu-processing-fixture.json'
    write(processing, receipt)
    write(output / 'physical-visibility-review.json', {
        'reviewer': 'synthetic CPU fixture', 'synthetic_fixture': True,
        'physical_completion': True, 'video_sha256': sha(raw_dir / 'raw.mkv'),
        'frame_map_sha256': sha(output / 'video_frames.jsonl'),
        'visible_and_reviewed': ['complete_vehicle', 'governed_curb',
                                 'official_device_face', 'worksite_activity',
                                 'commercial_classification_source',
                                 'unladen_weight_source', 'adjacent_place_source']})
    if args.negative:
        with (output / 'original-service-parking.jsonl').open('a') as stream:
            stream.write('{}\n')
    print(json.dumps(audit(output, processing, args.case, synthetic_fixture=True), indent=2))


if __name__ == '__main__':
    run()
