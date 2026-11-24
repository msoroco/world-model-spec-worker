"""Synthetic capture lifecycle ordering proof; no physical acceptance."""
import argparse
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--tag', default='')
    args = parser.parse_args()
    sys.path.insert(0, 'runtime')
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from scenario_pipeline.worker_exchange.saved_processing import (
        record_native_exit, acknowledge_owner_release, _closure)

    source = args.scratch / (args.tag + 'source-' + args.case)
    stage = args.scratch / ('lifecycle-' + args.case)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl',
                 'construction.json', 'runner.py'):
        shutil.copyfile(source / name, stage / name)
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    frames = len((source / 'video_frames.jsonl').read_text().splitlines())
    seal = seal_capture(stage, frames=frames, restoration={'restored': True},
                        errors=[], encoder_exit_codes={'diagnostic': 0})
    assert seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
    rejected = False
    try:
        acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    except ValueError:
        rejected = True
    assert rejected, 'Premature owner release was accepted'
    record_native_exit(stage)
    acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    _closure(stage, stage / 'owner-release.json', 'synthetic_fixture', True)
    events = seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']
    print(json.dumps({'case': args.case, 'events': events,
                      'premature_owner_release_rejected': rejected,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
