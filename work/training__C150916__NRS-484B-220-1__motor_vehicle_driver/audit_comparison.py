"""Check source-bound one-way comparison isolation and direction change."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(comparison, output, right_override=None):
    if comparison != HERE.name + '__comparison':
        raise ValueError('Unknown exact comparison')
    suffixes = ('designated', right_override or 'opposite')
    roots = [SCRATCH / f'c150916-saved-attempt-{suffix}' for suffix in suffixes]
    for root in roots:
        if not root.is_dir():
            raise ValueError('Missing comparison source: ' + str(root))
    poses = [rows(root / 'vehicle-pose.jsonl') for root in roots]
    traces = [rows(root / 'trace.jsonl') for root in roots]
    checks = {
        'same_original_road': sha(roots[0] / 'road.xodr') == sha(roots[1] / 'road.xodr'),
        'same_one_way_source': sha(roots[0] / 'source_context/one_way_designation.txt') == sha(roots[1] / 'source_context/one_way_designation.txt'),
        'same_sign_authority_source': sha(roots[0] / 'source_context/sign_authority.txt') == sha(roots[1] / 'source_context/sign_authority.txt'),
        'same_sign_governance_source': sha(roots[0] / 'source_context/sign_governance.txt') == sha(roots[1] / 'source_context/sign_governance.txt'),
        'same_frame_map': sha(roots[0] / 'video_frames.jsonl') == sha(roots[1] / 'video_frames.jsonl'),
        'both_600_frames': all(len(p) == 600 for p in poses) and all(len(t) == 600 for t in traces),
        'direction_setting_changed': poses[0][0]['requested_direction'] == 'designated' and poses[1][0]['requested_direction'] == 'opposite',
        'measured_motion_opposed': traces[0][-1]['position_m'][0] > traces[0][0]['position_m'][0] and traces[1][-1]['position_m'][0] < traces[1][0]['position_m'][0],
        'same_capture_profile': all(sha(roots[0] / name) == sha(roots[1] / name) for name in ('video_frames.jsonl',)),
        'synthetic_scope_retained': all(json.loads((root / 'road-review.json').read_text())['synthetic_diagnostic'] for root in roots)
    }
    if not all(checks.values()):
        raise ValueError('Selected comparison source differs from planned isolation: ' + str(checks))
    report = {'format': 'nrs-484b-220-1-comparison-audit-v1',
              'comparison_id': comparison, 'case_ids': [HERE.name + '__' + s for s in suffixes],
              'source_sha256': [{name: sha(root / name) for name in
                                 ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl', 'road.xodr')}
                                for root in roots], 'checks': checks, 'passed': True,
              'diagnostic_fixture': True, 'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison': comparison, 'passed': True, 'checks': checks}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--right-override', choices=('designated', 'opposite'))
    args = parser.parse_args()
    audit(args.comparison, args.output, args.right_override)
