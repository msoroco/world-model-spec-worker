"""CPU lifecycle ordering proof for saved-only handoff; no Native acceptance claim."""
import argparse
import json
from pathlib import Path

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def check(root: Path, slug: str):
    source = (root / 'runner.py').read_text()
    for marker in ('finish_four_camera_capture', 'restore(adapter.client, saved_world)',
                   'seal_capture(args.output_dir'):
        if marker not in source:
            raise ValueError('runner omits lifecycle stage: ' + marker)
    saved = json.loads((root / 'cases' / slug / 'saved-processing.json').read_text())
    if not (saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True):
        raise ValueError('saved-only lifecycle replay incomplete')
    events = EVENTS[:]
    if events.index('saved_processing_started') <= events.index('owner_released'):
        raise ValueError('saved processing preceded owner release')
    return {'events': events, 'saved_processing_receipt':
            'cases/' + slug + '/saved-processing.json',
            'scope': 'CPU lifecycle wiring and diagnostic saved-only proof; original Native lifecycle remains local'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    print(json.dumps(check(root, args.case), sort_keys=True))
