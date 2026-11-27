"""Exercise both planned grids against sealed 900-frame original-shaped sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import audit_sweep

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work/c150099-grid-comparison-v1'


def write_history(case_id: str) -> dict:
    suffix = case_id.removeprefix(ROOT.name + '__')
    spec = json.loads((ROOT / ('diagnostic-' + suffix + '.json')).read_text())
    rows = [json.loads(line) for line in spec['files']['original-attempt/history.jsonl'].splitlines()]
    inventory = json.loads(spec['files']['original-attempt/inventory.json'])
    path = SCRATCH / (suffix + '.jsonl')
    with path.open('w') as stream:
        for index in range(900):
            row = dict(rows[min(index, len(rows) - 1)])
            frame = rows[0]['original_frame'] + index
            row['original_frame'] = frame
            row['time_s'] = round(rows[0]['time_s'] + index * 0.05, 6)
            row['camera_frames'] = {name: dict(packet, original_frame=frame)
                                    for name, packet in row['camera_frames'].items()}
            stream.write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
    return {'case_id': case_id, 'history_path': str(path),
            'history_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'site_sha256': inventory['site_sha256']}


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    results = []
    for comparison in plan['comparisons']:
        if comparison['comparison_id'] not in (
                'conflict_necessity_source_review_grid',
                'designation_posting_source_review_grid'):
            continue
        sources = [write_history(case_id) for case_id in comparison['case_ids']]
        report = audit_sweep(plan, comparison['comparison_id'], sources)
        results.append(report)
        altered = [dict(item) for item in sources]
        altered[1]['site_sha256'] = '0' * 64
        try:
            audit_sweep(plan, comparison['comparison_id'], altered)
        except ValueError:
            pass
        else:
            raise ValueError('changed fixed site accepted')
        altered = [dict(item) for item in sources]
        altered[1] = dict(altered[0], case_id=altered[1]['case_id'])
        try:
            audit_sweep(plan, comparison['comparison_id'], altered)
        except ValueError:
            pass
        else:
            raise ValueError('wrong original case join accepted')
        print('grid comparison and two negative probes passed:', comparison['comparison_id'])
    if len(results) != 2:
        raise ValueError('two planned grid comparisons required')
    output = {'format': 'worker-grid-comparison-diagnostics',
              'comparisons': results, 'negative_probes': 4,
              'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
    (ROOT / 'cpu-grid-comparison-diagnostics.json').write_text(
        json.dumps(output, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
