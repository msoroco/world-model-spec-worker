"""Run the C229954 source-bound meter only after Native capture ownership ends."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_saved_packet import build, packet_from_attempt
from physical_check import assess

BASE = 'training__C229954__NRS-484B-500__vehicle_stopping_person__selected_d67fe2ae__'


def _sources(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file()}


def process(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if not attempt.is_dir() or output.exists():
        raise ValueError('Use a retained saved attempt and fresh analysis output')
    if output == attempt or attempt in output.parents:
        raise ValueError('Analysis output must not rewrite original acquisition')
    config_path = attempt / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing required source: config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('case_id')
    if not isinstance(case_id, str) or not case_id.startswith(BASE):
        raise ValueError('Wrong exact saved case identity')
    suffix = case_id.removeprefix(BASE)
    activity = 'stop'
    for name in ('stand', 'park'):
        if suffix.startswith(name + '_'):
            activity, suffix = name, suffix.removeprefix(name + '_')
    if suffix not in ('condition_a', 'condition_b') or \
            config.get('activity_mode') != activity:
        raise ValueError('Saved activity or comparison condition differs')
    before = _sources(attempt)
    measured = build(attempt)
    physical = assess(packet_from_attempt(attempt))
    after = _sources(attempt)
    if before != after:
        raise ValueError('Original acquisition changed during saved analysis')
    result = {'format': 'worker-designated-stop-saved-measurement',
              'case_id': case_id, 'activity_mode_request': activity,
              'comparison_condition': suffix,
              'measurement': measured, 'physical_check': physical,
              'original_source_hashes': before,
              'accepted': False, 'legal_verdict_claimed': False,
              'physical_completion_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                 allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(process(args.attempt, args.output), sort_keys=True))
