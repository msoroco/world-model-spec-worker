"""Measure realized speed and traffic over the frozen road window."""
import argparse
from native_finalize import finalize
import json
import statistics
from pathlib import Path
from source_audit import audit_sources

from scenario import route


def assess(attempt):
    attempt = Path(attempt)
    cfg = json.loads((attempt/'config.json').read_text())
    rows = [json.loads(x) for x in (attempt/'physical_samples.jsonl').read_text().splitlines()]
    sources = audit_sources(attempt, cfg, rows)
    window = [r for r in rows if 100 <= r['position_m'][0] <= 300]
    speeds = [r['speed_mps'] for r in window]
    traffic = [r['other_traffic']['speed_mps'] for r in window]
    completion = bool(rows and rows[-1]['route_index'] >= len(route('ego'))-2)
    requested = cfg['case']['variable_assignments']['commanded_speed_mps']['value']
    realized = None if not speeds else statistics.mean(speeds)
    return {'format': 'reasonable-speed-capability-v1', 'case_id': cfg['selected_case_id'],
            'original_source_validation': sources,
            'requested_speed_mps': requested, 'realized_mean_speed_mps': realized,
            'realized_max_speed_mps': None if not speeds else max(speeds),
            'traffic_mean_speed_mps': None if not traffic else statistics.mean(traffic),
            'measurement_window': 'native ego x=100..300m; full raw series retained',
            'window_sample_count': len(window), 'route_completed': completion,
            'judgment_resolved': False,
            'decision': 'inspect_frozen_sweep_evidence' if len(window)>=20 and completion else 'repair_same_frozen_case',
            'follow_up_configuration': {'source': 'config.json', 'case_id': cfg['selected_case_id'],
                                        'preserve_requested_speed': True, 'new_attempt_required': not completion},
            'physical_acceptance': False,
            'unverified': ['native paved surface and width', 'full traffic context', 'camera visibility',
                           'mandatory capture coverage', 'encoded video validity']}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    report = assess(a.attempt)
    Path(a.output).write_text(json.dumps(report, indent=2) + '\n')
    finalize(a.attempt, report)
