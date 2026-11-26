"""Exercise physical taxi stop episode assessment on labeled CPU fixtures."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def assess(attempt, kind):
    source_names = ('trace.jsonl', 'video_frames.jsonl', 'observed-activity.jsonl')
    available = {name: sha(attempt / name) for name in source_names
                 if (attempt / name).is_file()}
    missing = sorted(set(source_names) - set(available))
    detail = {'fixture_kind': kind, 'physical_not_legal': True}
    status = 'unverified'
    intervals = []
    if not missing:
        trace = rows(attempt / 'trace.jsonl')
        mapping = rows(attempt / 'video_frames.jsonl')
        activity = rows(attempt / 'observed-activity.jsonl')
        if not (len(trace) == len(mapping) == len(activity) == 600):
            raise ValueError('Original taxi physical rows lack 600 joined frames')
        if any(t['frame'] != m['carla_frame'] or
               a['native_frame'] != t['frame'] or
               a['video_frame'] != m['video_frame'] or
               abs(t['time_s'] - m['time_s']) > 1e-6 or
               abs(a['time_s'] - t['time_s']) > 1e-6
               for t, m, a in zip(trace, mapping, activity)):
            raise ValueError('Original taxi physical frame/time join failed')
        stationary = all(abs(a['observed_speed_mps']) <= 0.1
                         for a in activity)
        active = [a for a in activity
                  if a['observed_activity'] != 'no_activity']
        status = 'met' if stationary and active else 'not_met'
        intervals = [{'first_frame': trace[0]['frame'],
                      'last_frame': trace[-1]['frame'],
                      'first_time_s': trace[0]['time_s'],
                      'last_time_s': trace[-1]['time_s']}]
        detail.update({'sample_count': len(trace),
                       'stationary_samples': sum(abs(a['observed_speed_mps']) <= 0.1
                                                 for a in activity),
                       'observed_activity_samples': len(active),
                       'engineering_stationary_tolerance_mps': 0.1,
                       'not_a_legal_duration_or_expedition_threshold': True})
    check = {'status': status,
             'method': 'original time-joined taxi stop and observed activity episode',
             'sources': available, 'intervals': intervals,
             'details': detail, 'missing_evidence': missing,
             'legal_verdict_claimed': False,
             'physical_causation_claimed': False}
    return {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': check},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'observed_activity_samples': {
                'value': detail['observed_activity_samples'], 'unit': 'frames',
                'method': check['method'], 'time_window': '600 frames / 30 s',
                'statistic': 'source-observed count',
                'reference': 'observed-activity.jsonl'}}
                if status == 'met' else {}),
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, choices=('probe_a', 'probe_b'))
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion',
                                 'missing_evidence'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = ROOT / '.runtime-work' / (
        'c394327-public-' + args.case + '-primary-road-v10')
    scratch = ROOT / '.runtime-work' / 'lead-current-audits'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='taxi-physical-') as temporary:
        fixture = Path(temporary)
        for name in ('trace.jsonl', 'video_frames.jsonl', 'observed-activity.jsonl'):
            shutil.copyfile(attempt / name, fixture / name)
        activity_path = fixture / 'observed-activity.jsonl'
        if args.kind == 'incomplete_motion':
            activity = rows(activity_path)
            for row in activity:
                row['observed_activity'] = 'no_activity'
            activity_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                             for row in activity))
        elif args.kind == 'missing_evidence':
            activity_path.unlink()
        result = assess(fixture, args.kind)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind,
                      'status': result['physical_checks']['maneuver']['status'],
                      'source_count': len(result['physical_checks']['maneuver']['sources'])},
                     allow_nan=False))


if __name__ == '__main__':
    main()
