"""CPU negatives for the unexecuted original-capture saved bridge."""
import json
import shutil
import tempfile
from pathlib import Path

from prepare_original import HERE, prepare, sha


def prove():
    errors = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / 'capture'
        source.mkdir()
        shutil.copyfile(HERE / 'drafts' / 'reference' / 'primary' / 'config.json',
                        source / 'config.json')
        report = {'case_suffix': 'reference', 'candidate_id': 'primary',
                  'frames': 479, 'error': None, 'restoration': {}, 'accepted': False}
        (source / 'native-capture-report.json').write_text(json.dumps(report))
        scenarios = [
            ('incomplete_capture', 'Native capture incomplete or unsealed'),
            ('wrong_lane_readback', 'Native initial lane readback differs'),
            ('missing_original_cameras', 'Original camera source absent'),
        ]
        for name, expected in scenarios:
            if name != 'incomplete_capture':
                report['frames'] = 480
                (source / 'native-capture-report.json').write_text(json.dumps(report))
            if name == 'missing_original_cameras':
                (source / 'native-map-readback.json').write_text(json.dumps(
                    {'observed_initial_lanes': {'subject': -1, 'approach': -1}}))
            elif name == 'wrong_lane_readback':
                (source / 'native-map-readback.json').write_text(json.dumps(
                    {'observed_initial_lanes': {'subject': -2, 'approach': -1}}))
            destination = root / ('saved-' + name)
            try:
                prepare(source, destination, 'reference', 'primary')
            except ValueError as exc:
                if str(exc) != expected or destination.exists():
                    raise
                errors.append({'case': name, 'error': expected})
            else:
                raise ValueError('Original bridge accepted incomplete source')
    result = {'format': 'c405647-1b-original-bridge-cpu-negatives-v1',
              'bridge_sha256': sha(HERE / 'prepare_original.py'),
              'negative_receipts': errors, 'original_positive_executed': False,
              'accepted_delivery': False}
    (HERE / 'original-bridge-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
