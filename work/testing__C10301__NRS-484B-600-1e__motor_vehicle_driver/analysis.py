"""Selected C10301 measurements from original sealed Native sources.

The sampled speed relation and source-bound operation context are observations,
not a legal finding or a claim about peaks between 20 Hz samples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit_decoded_media
from speed_boundary import measure


def _source(attempt: Path, name: str) -> tuple[dict, str]:
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def measure_operation(attempt: Path, case_id: str) -> dict:
    setup, _ = _source(attempt, 'authored-setup.json')
    site, site_sha = _source(attempt, 'native-site-source.json')
    motion, _ = _source(attempt, 'native-motion-receipt.json')
    if (setup.get('case_id') != case_id or site.get('case_id') != case_id or
            motion.get('case_id') != case_id or
            setup.get('actor') != 'motor_vehicle_driver' or
            site.get('actor') != setup['actor'] or
            setup.get('native_site_sha256') != site_sha or
            motion.get('sample_count') != 900):
        raise ValueError('original vehicle operation source identity differs')
    return {'actor': setup['actor'], 'vehicle_blueprint_id': site['vehicle_blueprint_id'],
            'observed_motion_samples': motion['sample_count'],
            'travel_m': motion['travel_m'],
            'territorial_applicability': 'unresolved'}


def measure_rate(attempt: Path, case_id: str) -> dict:
    observed = measure(attempt, case_id)
    return {'peak_sample_mph': observed['peak_sample_mph'],
            'sampled_relation': observed['sampled_relation'],
            'peak_uncertainty_mph': observed['peak_uncertainty_mph'],
            'between_sample_peaks': observed['between_sample_peaks'],
            'sample_count': observed['sample_count']}


def finalize(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt)
    media = audit_decoded_media(attempt, case_id,
                                allow_diagnostic=allow_diagnostic)
    requirements = (
        ('vehicle_operation', measure_operation,
         ('authored-setup.json', 'native-site-source.json', 'native-motion-receipt.json')),
        ('sampled_rate_boundary', measure_rate,
         ('original-speed.jsonl', 'speed-source.json')),
    )
    measurements = {}
    for key, method, sources in requirements:
        value = method(attempt, case_id)
        hashes = {}
        for name in sources:
            path = attempt / name
            if not path.is_file():
                raise ValueError('Missing required source: ' + name)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        measurements[key] = {'method': method.__name__, 'value': value,
                             'sources': hashes}
    return {'case_id': case_id, 'measurements': measurements,
            'full_video_decode': media['full_video_decode'],
            'physical_acceptance_claimed': False,
            'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    config, _ = _source(args.attempt, 'config.json')
    report = finalize(args.attempt, config['selected_case_id'],
                      allow_diagnostic=args.allow_diagnostic)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
