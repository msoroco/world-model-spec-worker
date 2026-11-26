"""Check the source-level Native release ordering before saved processing."""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    runner = (root / 'draft-native/runner.py').read_text()
    saved = (root / 'native/saved_measure.py').read_text()
    points = ['sensor.stop()', 'encoder.stdin.close()', 'actor.destroy()',
              'restore(client, original_world)']
    indices = [runner.find(point) for point in points]
    if any(index < 0 for index in indices) or indices != sorted(indices):
        raise ValueError('Native resource cleanup ordering changed')
    if 'from build_saved_packet import build' not in saved or \
            'from physical_check import assess' not in saved or \
            'def process(attempt, output):' not in saved:
        raise ValueError('Saved-only processing source missing')
    events = ['capture_finished', 'encoders_closed',
              'restoration_verified', 'native_exit',
              'owner_released', 'saved_processing_started']
    print(json.dumps({'events': events, 'scope': 'source-level CPU ordering only',
                      'native_lifecycle_executed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
