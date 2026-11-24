"""Tamper tests for the independent branch comparison source audit."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from branch_comparison_audit import BASE, HERE, grid, placement


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_case(source, target, placement_case=False):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / 'config.json', target / 'config.json')
    if placement_case:
        shutil.copyfile(source / 'placement-record.json', target / 'placement-record.json')
    else:
        (target / 'raw-fixture').mkdir(exist_ok=True)
        shutil.copyfile(source / 'raw-fixture/native-raw-actors.jsonl',
                        target / 'raw-fixture/native-raw-actors.jsonl')


def main():
    with tempfile.TemporaryDirectory(prefix='c10389-comparison-proof-', dir=HERE.parents[1] / '.runtime-work') as name:
        root = Path(name)
        for suffix in ('signal_red_proceed', 'signal_red_stop',
                       'signal_green_proceed', 'signal_green_stop'):
            copy_case(BASE / suffix, root / suffix)
        source = root / 'signal_red_stop/raw-fixture/native-raw-actors.jsonl'
        lines = source.read_text().splitlines();row = json.loads(lines[0])
        row['signal_state_observed'] = 'TrafficLightState.Green'
        lines[0] = json.dumps(row)
        source.write_text('\n'.join(lines) + '\n')
        try:
            grid('signal', root)
        except ValueError as exc:
            assert 'Grid condition source differs' in str(exc)
        else:
            raise AssertionError('Altered signal state accepted')
        for suffix in ('placement_record_absent', 'placement_record_supplied'):
            copy_case(BASE / suffix, root / suffix, True)
        source = root / 'placement_record_supplied/placement-record.json'
        record = json.loads(source.read_text());record['official_placement_verified'] = True
        source.write_text(json.dumps(record) + '\n')
        try:
            placement(root)
        except ValueError as exc:
            assert 'claims authority' in str(exc)
        else:
            raise AssertionError('Authored placement status promoted to authority')
    main_proof = BASE / 'branch-comparison-proof.json'
    proof = {'format': 'c10389-branch-comparison-negative-proof-v1',
             'positive_proof_sha256': sha(main_proof),
             'altered_signal_state_rejected': True,
             'unverified_placement_authority_rejected': True,
             'synthetic_only': True, 'legal_outcome_claimed': False}
    path = BASE / 'branch-comparison-negative-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(main()))
