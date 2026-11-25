"""Audit exact pinned saved cases and fixed comparison conditions.

This checks software fixtures only. It does not turn their source hashes into
reviewed original highway, sign, or physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import FIXED
from one_way_direction import CASES
from runner import check_config


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/c147311-nov25d'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    manifest = json.loads((HERE / 'diagnostic-execution-manifest.json').read_text())
    entries = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((HERE / 'case-plan.json').read_text())
    seen = {}
    for case in CASES:
        case_id = HERE.name + '__' + case.name
        entry = entries[case_id]
        attempt = SCRATCH / ('pinned-' + case.name + '-v8')
        saved = SCRATCH / ('saved-' + case.name + '-v8') / 'v0001'
        config = json.loads((attempt / 'config.json').read_text())
        check_config(config)
        if sha(attempt / 'construction.json') != entry['construction_sha256']:
            raise ValueError('selected construction hash changed: ' + case.name)
        processing = json.loads((saved / 'processing.json').read_text())
        result_path = saved / 'analysis' / 'result.json'
        result = json.loads(result_path.read_text())
        scene = json.loads((attempt / 'site-source.json').read_text())
        measured = result['measured_values']
        if (processing['case_id'] != case_id or processing['passed'] is not True
                or processing['recorded_only'] is not True
                or processing['native_revision']['construction_sha256'] != entry['construction_sha256']
                or result['case_id'] != case_id or measured['frame_count'] != 900
                or measured['actual_direction'] != case.direction
                or scene['lane'] != case.lane or scene['direction'] != case.direction
                or scene.get('diagnostic_fixture') is not True):
            raise ValueError('pinned saved case/source measurement differs: ' + case.name)
        seen[case_id] = {'case': case, 'scene': scene, 'result_sha256': sha(result_path),
                         'construction_sha256': entry['construction_sha256']}
    comparisons = []
    for pair in plan['comparisons']:
        a, b = (seen[case_id] for case_id in pair['case_ids'])
        for field in FIXED:
            key = field + '_source_sha256'
            if a['scene'][key] != b['scene'][key]:
                raise ValueError('fixed source context differs: ' + field)
        if pair['comparison_id'].startswith('actual_direction_'):
            if a['case'].lane != b['case'].lane or a['case'].direction == b['case'].direction:
                raise ValueError('actual direction variable not isolated')
        elif a['case'].lane == b['case'].lane or a['case'].direction != b['case'].direction:
            raise ValueError('lane variable not isolated')
        comparisons.append({'comparison_id': pair['comparison_id'],
                            'case_ids': pair['case_ids'],
                            'saved_result_sha256': [a['result_sha256'], b['result_sha256']],
                            'construction_sha256': [a['construction_sha256'], b['construction_sha256']],
                            'variable_isolated': True})
    receipt = {'format': 'c147311-pinned-diagnostic-comparison-audit-v1',
               'assignment_id': HERE.name, 'manifest_sha256': sha(HERE / 'diagnostic-execution-manifest.json'),
               'source_kind': 'synthetic_software_fixture', 'original_acceptance_claimed': False,
               'comparisons': comparisons}
    (HERE / 'diagnostic-comparison-receipts.json').write_text(
        json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
