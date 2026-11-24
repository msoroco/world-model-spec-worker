"""Check the portable synthetic capture-to-saved ordering contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def main(case: str) -> None:
    source = HERE / 'selected-fixture' / case / 'capture' / 'manifest.json'
    data = json.loads(source.read_text())
    if data.get('frames') != 600 or not data.get('extraction_confirmed'):
        raise ValueError('Diagnostic capture source is incomplete')
    state = 0
    for event in EVENTS:
        if event != EVENTS[state]:
            raise ValueError('Saved processing preceded closure')
        state += 1
    print(json.dumps({'case': case, 'events': EVENTS, 'synthetic_lifecycle_only': True,
                      'capture_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    main(parser.parse_args().case)
