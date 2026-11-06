"""Produce reproducible CPU-only receipts for three unselected boundary drafts."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'native'))
from measure_after_turn import measure  # noqa: E402
from test_measure_after_turn import GEOMETRY, fixture  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE/'case-plan.json').read_text())
    assignment = ROOT/'inputs'/plan['assignment_id']/'assignment.json'
    if sha(assignment) != next(s['sha256'] for s in plan['sources'] if s['path'].endswith('/assignment.json')):
        raise ValueError('Frozen assignment source hash changed')
    out = HERE/'draft-measurements'
    out.mkdir(exist_ok=True)
    geometry = out/'native-geometry-draft.json'
    map_path = HERE/'draft-construction'/'scene.xodr'
    if not map_path.is_file():
        raise ValueError('Saved authored OpenDRIVE source missing')
    native_geometry = dict(GEOMETRY, authored_map_sha256=sha(map_path))
    geometry.write_text(json.dumps(native_geometry, indent=2)+'\n')
    summary = []
    for case in plan['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        samples = out/(suffix+'-synthetic-native-samples.jsonl')
        samples.write_text(''.join(json.dumps(row, sort_keys=True)+'\n'
                              for row in fixture(case['requested_setting'])))
        receipt = measure(samples, geometry)
        receipt.update(case_id=case['case_id'], requested_setting_ft=case['requested_setting'],
                       draft_only=True, selected=False, source_assignment_sha256=sha(assignment),
                       authored_route_sha256=sha(HERE/'draft-construction'/f'route-{suffix}.json'))
        path = out/(suffix+'-measurement.json')
        path.write_text(json.dumps(receipt, indent=2)+'\n')
        summary.append({'case_id': case['case_id'], 'relation': receipt['threshold_relation'],
                        'interval_m': receipt['distance_interval_m'], 'receipt_sha256': sha(path)})
    if [row['relation'] for row in summary] != ['within_50_feet', 'unresolved_at_50_feet', 'exceeds_50_feet']:
        raise ValueError('Controlled threshold probes lost expected ordering')
    print(json.dumps({'status':'synthetic_cpu_draft_only', 'source_assignment_sha256':sha(assignment),
                      'cases':summary}, indent=2))


if __name__ == '__main__':
    main()
