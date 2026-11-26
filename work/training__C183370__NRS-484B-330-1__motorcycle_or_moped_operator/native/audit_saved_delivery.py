"""Join saved motorcycle motion, four decoded cameras, and review bindings.

This is a CPU audit of original sources. It never infers that a signal was
visible, a flagger was authorized, or a legal outcome followed.
"""

import argparse
import json
from pathlib import Path

from audit_media import audit_media
from measure_original import measure
from review_original import review


ASSIGNMENT = 'training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator'


def audit(attempt, config_path, receipt_path):
    config = json.loads(Path(config_path).read_text())
    case_id = config.get('case_id')
    if (config.get('assignment_id') != ASSIGNMENT or
            case_id not in (ASSIGNMENT + '__probe_a', ASSIGNMENT + '__probe_b') or
            config.get('law_id') != 'NRS-484B-330-1' or
            config.get('cell_id') != 'C183370' or
            config.get('actor') != 'motorcycle_or_moped_operator' or
            config.get('frame_count') != 600 or
            config.get('rate_hz') != 20 or
            config.get('duration_s') != 30):
        raise ValueError('Exact saved delivery case or duration differs')
    suffix = case_id.rsplit('__', 1)[1]
    canonical = json.loads((Path(__file__).resolve().parent /
                            suffix / 'config.json').read_text())
    if config != canonical:
        raise ValueError('Saved delivery config differs from exact construction')
    measured = measure(attempt, case_id)
    media = audit_media(attempt, config['cameras'], 600)
    reviewed = review(attempt, case_id, receipt_path)
    if reviewed['source_seal_sha256'] != measured['source_seal_sha256']:
        raise ValueError('Saved measurement and review source seals differ')
    return {
        'format': 'c183370-saved-delivery-audit-v1',
        'case_id': case_id,
        'source_seal_sha256': measured['source_seal_sha256'],
        'measurement': measured,
        'camera_decode': media['cameras'],
        'review_binding': reviewed,
        'source_join_passed': True,
        'original_pixels_independently_verified': False,
        'physical_completion': None,
        'legal_verdict': None,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        raise ValueError('Fresh saved delivery audit output required')
    result = audit(args.attempt, args.config, args.receipt)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'source_join_passed': True}))
