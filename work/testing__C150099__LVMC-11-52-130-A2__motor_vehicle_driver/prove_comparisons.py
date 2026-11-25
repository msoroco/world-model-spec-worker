"""Exercise eight independent comparison audits on 900-frame synthetic histories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TEMP = REPO / '.runtime-work/c150099-comparison-source-v1'


def serial(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(case_id: str) -> dict:
    suffix = case_id.removeprefix(ROOT.name + '__')
    spec = json.loads((ROOT / ('diagnostic-' + suffix + '.json')).read_text())
    original = [json.loads(line) for line in spec['files']['original-attempt/history.jsonl'].splitlines()]
    inventory = json.loads(spec['files']['original-attempt/inventory.json'])
    history = TEMP / (suffix + '.jsonl')
    if history.exists():
        raise ValueError('retain previous comparison source; choose fresh proof version')
    TEMP.mkdir(parents=True, exist_ok=True)
    with history.open('x') as stream:
        for index in range(900):
            row = dict(original[min(index, len(original) - 1)])
            frame = original[0]['original_frame'] + index
            row['original_frame'] = frame
            row['time_s'] = round(original[0]['time_s'] + index * 0.05, 6)
            row['camera_frames'] = {name: dict(packet, original_frame=frame)
                                    for name, packet in row['camera_frames'].items()}
            stream.write(serial(row))
    return {'case_id': case_id, 'history_path': str(history),
            'history_sha256': sha(history), 'site_sha256': inventory['site_sha256']}


def main() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = {case_id for comparison in plan['comparisons']
             for case_id in comparison['case_ids']}
    sources = {case_id: source(case_id) for case_id in sorted(cases)}
    receipts = []
    for comparison in plan['comparisons']:
        left, right = [sources[case_id] for case_id in comparison['case_ids']]
        proof = audit_pair(plan, comparison['comparison_id'], left, right)
        proof['diagnostic_fixture'] = True
        proof['physical_acceptance_claimed'] = False
        receipts.append(proof)
        print('comparison audit passed:', comparison['comparison_id'], flush=True)
    (ROOT / 'cpu-comparison-diagnostics.json').write_text(
        json.dumps({'format': 'worker-comparison-diagnostics',
                    'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                    'comparisons': receipts}, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
