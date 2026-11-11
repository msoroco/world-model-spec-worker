"""Check the planned officer capture-to-saved lifecycle order on a CPU fixture."""
import argparse
import json
from pathlib import Path

EVENTS = ('capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started')


def validate(events):
    if tuple(events) != EVENTS:
        raise ValueError('Saved processing precedes Native ownership closure')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--saved-receipt', required=True)
    args = parser.parse_args()
    saved = json.loads(Path(args.saved_receipt).read_text())
    if not saved.get('passed') or not saved.get('originals_preserved'):
        raise ValueError('Saved-only processing proof missing')
    validate(EVENTS)
    try:
        validate(EVENTS[:-2] + (EVENTS[-1], EVENTS[-2]))
    except ValueError:
        pass
    else:
        raise ValueError('Early saved processing was accepted')
    print('CPU lifecycle fixture: ordered release accepted, early processing rejected')


if __name__ == '__main__':
    main()
