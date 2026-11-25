"""Check the two exact parking comparison pairs against original sources."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / '.runtime-work'
PAIRS = {
    'witness_comparison': ('witness_1', 'witness_2'),
    'exception_1_comparison': ('exception_1_1', 'exception_1_2')
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_road(path):
    root = ET.fromstring(path.read_text())
    for road in root.findall('road'):
        signals = road.find('signals')
        if signals is not None:
            signals.clear()
    return ET.tostring(root)


def audit(comparison, output, right_override=None):
    prefix = HERE.name + '__'
    if not comparison.startswith(prefix) or comparison[len(prefix):] not in PAIRS:
        raise ValueError('Unknown exact comparison')
    left_name, right_name = PAIRS[comparison[len(prefix):]]
    if right_override:
        right_name = right_override
    roots = [SCRATCH / f'nrs497-saved-attempt-{name}' for name in (left_name, right_name)]
    for root in roots:
        if not root.is_dir():
            raise ValueError('Missing comparison source: ' + str(root))
    checks = {
        'same_original_pose': sha(roots[0] / 'vehicle-pose.jsonl') == sha(roots[1] / 'vehicle-pose.jsonl'),
        'same_original_trace': sha(roots[0] / 'trace.jsonl') == sha(roots[1] / 'trace.jsonl'),
        'same_original_frame_map': sha(roots[0] / 'video_frames.jsonl') == sha(roots[1] / 'video_frames.jsonl'),
        'same_one_way_source': sha(roots[0] / 'source_context/one_way_designation.txt') == sha(roots[1] / 'source_context/one_way_designation.txt'),
        'same_street_boundary_source': sha(roots[0] / 'source_context/street_boundary.txt') == sha(roots[1] / 'source_context/street_boundary.txt'),
        'same_road_except_permission_signal': fixed_road(roots[0] / 'road.xodr') == fixed_road(roots[1] / 'road.xodr'),
        'permission_signal_changed': sha(roots[0] / 'road.xodr') != sha(roots[1] / 'road.xodr')
    }
    reviews = [json.loads((root / 'road-review.json').read_text()) for root in roots]
    checks['device_presence_changed'] = reviews[0]['permission_device_present'] != reviews[1]['permission_device_present']
    checks['one_way_context_fixed'] = all(r['roadway_is_laned'] and r['roadway_is_one_way'] for r in reviews)
    checks['synthetic_scope_retained'] = all(r['synthetic_diagnostic'] for r in reviews)
    if not all(checks.values()):
        raise ValueError('Selected comparison source differs from planned isolation: ' + str(checks))
    report = {'format': 'nrs-484b-497-comparison-audit-v1', 'comparison_id': comparison,
              'case_ids': [prefix + left_name, prefix + right_name],
              'source_sha256': [{name: sha(root / name) for name in
                                 ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl', 'road.xodr')}
                                for root in roots],
              'checks': checks, 'passed': True, 'diagnostic_fixture': True,
              'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison': comparison, 'passed': True, 'checks': checks}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--right-override', choices=('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'))
    args = parser.parse_args()
    audit(args.comparison, args.output, args.right_override)
