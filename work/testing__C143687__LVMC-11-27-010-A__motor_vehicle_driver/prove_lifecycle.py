"""Exercise pinned Native closure order on diagnostic source copies."""
import argparse
import json
import shutil
import sys
from pathlib import Path

from prove_physical import CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'runtime')
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    from scenario_pipeline.worker_exchange.saved_processing import (
        record_native_exit, acknowledge_owner_release, _closure)

    package = Path(__file__).resolve().parent
    stage = args.scratch / ('lifecycle-' + args.case)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    spec = json.loads((package / ('diagnostic-' + args.case + '.json')).read_text())
    for name in ('trace.jsonl', 'video_frames.jsonl'):
        (stage / name).write_text(spec['files'][name])
    for name in ('config.json', 'construction.json', 'runner.py'):
        shutil.copyfile(package / 'cases' / args.case / name, stage / name)
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture'}) + '\n')
    seal = seal_capture(stage, frames=900, restoration={'restored': True},
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
