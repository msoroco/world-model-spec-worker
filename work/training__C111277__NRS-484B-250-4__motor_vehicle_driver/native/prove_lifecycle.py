"""Exercise source sealing, Native exit and owner-release ordering on CPU fixtures."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def run(letter):
    source = REPO / '.runtime-work' / f'c111277-compat-new-{letter}-primary'
    stage = REPO / '.runtime-work' / f'c111277-lifecycle-{letter}'
    stage.mkdir(parents=True, exist_ok=True)
    for name in ('construction.json', 'runner.py', 'trace.jsonl', 'video_frames.jsonl',
                 'acquisition-provenance.json'):
        shutil.copy2(source / name, stage / name)
    try:
        record_native_exit(stage)
    except (FileNotFoundError, ValueError):
        print('pre-seal Native exit correctly rejected')
    else:
        raise AssertionError('Native exit accepted without a seal')
    seal = seal_capture(stage, frames=600, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={'overview': 0, 'approach': 0,
                                            'reference_corner': 0, 'driver_reference': 0})
    native_exit = record_native_exit(stage)
    owner = acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    if not (seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
            and native_exit['event'] == 'native_exit' and owner['event'] == 'owner_released'):
        raise AssertionError('lifecycle order failed')
    print(json.dumps({'events': seal['events'] + ['native_exit', 'owner_released',
                                                  'saved_processing_started'],
                      'exit_code': 0, 'diagnostic_fixture': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--letter', required=True, choices=['a', 'b'])
    run(parser.parse_args().letter)
