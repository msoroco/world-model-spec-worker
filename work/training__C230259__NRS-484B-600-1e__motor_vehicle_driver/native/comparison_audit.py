"""Independent, saved-only comparison of the three absolute-speed observations."""
import argparse
import json
from pathlib import Path

from measure_absolute_speed import AID, CAMERAS, CAP_MPH, sha

PROBES = ('probe_01', 'probe_02', 'probe_03')
FIXED = ('route_source', 'vehicle_identity_source', 'driving_state_source')
SOURCES = {'road_context.json', 'video_frames.jsonl', 'native_motion.jsonl'} | {'camera_'+name+'.mkv' for name in CAMERAS}


def audit(source_dirs, observation_paths):
    if len(source_dirs) != 3 or len(observation_paths) != 3:
        raise ValueError('Three exact speed cases required')
    rows = []
    for probe, source_dir, observation_path in zip(PROBES, source_dirs, observation_paths):
        source_dir, observation_path = Path(source_dir), Path(observation_path)
        context_path = source_dir/'road_context.json'
        if not context_path.is_file() or not observation_path.is_file():
            raise ValueError('Missing saved comparison source or observation: '+probe)
        context = json.loads(context_path.read_text())
        observed = json.loads(observation_path.read_text())
        if context.get('assignment_id') != AID or observed.get('assignment_id') != AID:
            raise ValueError('Comparison assignment mismatch: '+probe)
        if context.get('case_id') != AID+'__'+probe:
            raise ValueError('Comparison case identity missing: '+probe)
        if observed.get('format') != 'saved-absolute-speed-observation' or observed.get('review_kind') != 'original_source_review':
            raise ValueError('Comparison requires original saved-source observation: '+probe)
        sources = observed.get('sources', {})
        if sources.get('road_context.json') != sha(context_path):
            raise ValueError('Comparison observation context hash stale: '+probe)
        if set(sources) != SOURCES or any(not (source_dir/name).is_file() or sha(source_dir/name) != sources[name] for name in SOURCES):
            raise ValueError('Comparison observation source hash stale: '+probe)
        if observed.get('statutory_cap_mph') != CAP_MPH or observed.get('sample_count') != 600 or observed.get('driving_frame_count') != 600:
            raise ValueError('Comparison measurement contract differs: '+probe)
        if observed.get('physical_acceptance_claimed') is not False or observed.get('legal_verdict_claimed') is not False:
            raise ValueError('Comparison carries unsupported acceptance claim: '+probe)
        fixed = tuple(context.get(key) for key in FIXED)
        if any(not value for value in fixed):
            raise ValueError('Comparison missing fixed-condition source: '+probe)
        maximum = observed.get('maximum_observed_mph_while_driving')
        if type(maximum) not in (int, float):
            raise ValueError('Comparison missing observed speed: '+probe)
        rows.append({'case_id': AID+'__'+probe, 'maximum_observed_mph': maximum,
                     'above_cap_frame_count': len(observed.get('frames_above_80_mph', [])),
                     'fixed': fixed, 'observation_sha256': sha(observation_path)})
    if len({row['fixed'] for row in rows}) != 1:
        raise ValueError('Comparison fixed route, vehicle or driving source differs')
    values = [row['maximum_observed_mph'] for row in rows]
    if not (values[0] < CAP_MPH and abs(values[1]-CAP_MPH) <= 1e-9 and values[2] > CAP_MPH):
        raise ValueError('Measured below, at and above boundary not established')
    if rows[0]['above_cap_frame_count'] or rows[1]['above_cap_frame_count'] or not rows[2]['above_cap_frame_count']:
        raise ValueError('Above-cap frame evidence contradicts measured boundary')
    return {'format': 'worker-speed-comparison-audit', 'assignment_id': AID,
            'fixed_conditions': list(FIXED), 'cases': [{k: v for k, v in row.items() if k != 'fixed'} for row in rows],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dirs', nargs=3, required=True, type=Path)
    parser.add_argument('--observations', nargs=3, required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.source_dirs, args.observations), indent=2)+'\n')
