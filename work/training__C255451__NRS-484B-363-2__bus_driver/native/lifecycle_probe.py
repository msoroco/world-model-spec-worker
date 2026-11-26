"""Rehearse Native ownership closure before saved processing on CPU evidence."""
import argparse
import json
from pathlib import Path

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def prove(runner, processing):
    code = Path(runner).read_text()
    markers = ('native_frame = world.tick()', 'proc.stdin.close()',
               'core_capture.close(confirmed=True)', 'actor.destroy()',
               'world.apply_settings(settings)')
    positions = [code.find(marker) for marker in markers[:-1]] + [code.rfind(markers[-1])]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError('Native runner does not close acquisition before restoring ownership')
    receipt = json.loads(Path(processing).read_text())
    if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or receipt.get('missing_evidence')):
        raise ValueError('Saved processing did not follow complete original closure rehearsal')
    return {'events': EVENTS, 'exit_code': 0, 'scope': 'synthetic CPU ownership rehearsal',
            'native_executed': False, 'saved_processing_receipt': str(processing)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runner', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prove(args.runner, args.processing)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(' > '.join(result['events']))


if __name__ == '__main__':
    main()
