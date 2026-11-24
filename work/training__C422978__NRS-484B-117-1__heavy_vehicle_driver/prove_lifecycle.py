"""Verify the source order of capture cleanup and a CPU owner-release mock."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def prove(case):
    source = HERE / 'native/runner.py'
    code = source.read_text()
    markers = ["if frames != 600:", "process.stdin.close()",
               "restored = restore(client, saved)", "if error:"]
    positions = [code.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert case in {HERE.name + '__reference', HERE.name + '__contrast'}
    # The two final events are a unit mock of the external owner protocol.
    return {'case_id': case, 'events': EVENTS,
            'runner_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'external_owner_events_mocked': EVENTS[-2:],
            'original_native_executed': False, 'source_order_verified': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    print(json.dumps(prove(parser.parse_args().case), indent=2, sort_keys=True))
