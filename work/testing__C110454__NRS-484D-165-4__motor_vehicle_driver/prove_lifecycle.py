"""Exercise synthetic capture closure, Native exit, release, saved replay order."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from scenario_pipeline.worker_exchange.native_output import seal_capture
from scenario_pipeline.worker_exchange.saved_processing import (
    acknowledge_owner_release, record_native_exit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt).resolve(strict=True)
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('lifecycle output must be fresh')
    seal = seal_capture(attempt, frames=5, restoration={'restored': True},
                        errors=[], encoder_exit_codes={'four_view': 0})
    if seal['events'] != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('capture closure order differs')
    exit_receipt = record_native_exit(attempt)
    if exit_receipt['event'] != 'native_exit':
        raise ValueError('Native exit receipt missing')
    owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
    if owner['event'] != 'owner_released':
        raise ValueError('owner release receipt missing')
    command = [str(Path.cwd() / '.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
               '--manifest', args.manifest, '--case', args.case,
               '--attempt', str(attempt), '--output', str(output),
               '--library', 'runtime/library', '--validator', args.validator,
               '--owner-release-receipt', str(attempt / 'owner-release.json')]
    subprocess.run(command, check=True, timeout=300)
    if not (output / 'v0001' / 'processing.json').is_file():
        raise ValueError('saved processing did not start after owner release')
    print('capture_finished\nencoders_closed\nrestoration_verified\n'
          'native_exit\nowner_released\nsaved_processing_started')


if __name__ == '__main__':
    main()
