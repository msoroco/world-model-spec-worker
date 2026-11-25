"""CPU exercise of fixed fields, differences and negative comparison inputs."""

import hashlib
import json
import shutil
from pathlib import Path

from comparison_audit import audit_pair


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'testing__C376646__NRS-484B-250-4__motor_vehicle_driver__'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(suffix):
    return REPO / '.runtime-work' / ('c376646-compat-v6-' + suffix)


def counterfactual_clear(source_dir, target):
    """Isolate the other-prior predicate for an auditor unit test only."""
    target.mkdir(parents=True, exist_ok=False)
    for name in ('config.json', 'junction_context.json', 'video_frames.jsonl',
                 'vehicle_signal_history.jsonl'):
        shutil.copy2(source_dir / name, target / name)
    motion = target / 'vehicle_signal_history.jsonl'
    rows = [json.loads(line) for line in motion.read_text().splitlines()]
    rows[-1]['other']['body_vertices_xy_m'] = [[0.8, 11], [2.8, 11],
                                                  [0.8, 13], [2.8, 13]]
    motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (target / 'COUNTERFACTUAL.txt').write_text(
        'Synthetic auditor unit input: moved the other body after its prior stop; '
        'no Native motion or packet consistency claimed.\n')


def main():
    scratch = REPO / '.runtime-work/c376646-comparison-counterfactual-v1'
    if scratch.exists():
        shutil.rmtree(scratch)
    counterfactual_clear(source('stop_line_other_previously_stopped'), scratch)
    pairs = [
        ('stop_reference_hierarchy', 'stop_line_other_inside',
         'crosswalk_other_previously_stopped', source('crosswalk_other_previously_stopped')),
        ('stop_reference_hierarchy', 'crosswalk_other_previously_stopped',
         'nearest_view_other_inside', source('nearest_view_other_inside')),
        ('stop_halt_condition', 'stop_line_other_inside',
         'stop_line_no_halt', source('stop_line_no_halt')),
        ('other_priority_basis', 'stop_line_other_inside',
         'stop_line_other_previously_stopped', scratch),
    ]
    records = []
    for mode, left_suffix, right_suffix, right in pairs:
        left = source(left_suffix)
        passed = audit_pair(left, right, mode)
        if passed['observed_difference'] is not True or passed['physical_acceptance_claimed'] is not False:
            raise ValueError('Comparison audit made an unsupported claim')
        try:
            audit_pair(left, left, mode)
        except ValueError as error:
            negative = str(error)
        else:
            raise ValueError('Same-source comparison was accepted')
        if mode == 'other_priority_basis':
            try:
                audit_pair(left, source(right_suffix), mode)
            except ValueError as error:
                unisolated = str(error)
            else:
                raise ValueError('Unisolated original diagnostic was accepted')
        else:
            unisolated = None
        records.append({'comparison_id': mode, 'left_case_id': PREFIX + left_suffix,
                        'right_case_id': PREFIX + right_suffix,
                        'left_source_sha256': sha(left / 'vehicle_signal_history.jsonl'),
                        'right_source_sha256': sha(right / 'vehicle_signal_history.jsonl'),
                        'positive': passed, 'same_source_rejection': negative,
                        'unisolated_source_rejection': unisolated,
                        'counterfactual_unit_input': mode == 'other_priority_basis'})
    output = ROOT / 'comparison-proof.json'
    output.write_text(json.dumps({'format': 'worker-comparison-cpu-proof',
                                  'diagnostic_fixture': True,
                                  'physical_acceptance_claimed': False,
                                  'comparisons': records}, indent=2) + '\n')
    for row in records:
        print(row['comparison_id'], row['left_case_id'].split('__')[-1],
              row['right_case_id'].split('__')[-1], 'positive and negative passed',
              'counterfactual' if row['counterfactual_unit_input'] else 'selected diagnostic')


if __name__ == '__main__':
    main()
