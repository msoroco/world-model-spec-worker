"""Prove fixed conditions and a changed-source rejection for towing sweep."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from towing_sweep_comparison import audit


def main():
    roots = [REPO / '.runtime-work' / f'c160013-towing-sweep-{i}-primary-compat-v1'
             for i in range(3)]
    result = audit(roots)
    receipt = PACKAGE / 'cases/towing-sweep-comparison-diagnostic.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    stage = REPO / '.runtime-work/c160013-towing-sweep-comparison-negative'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ('road_context.json', 'caravan_history.jsonl',
                 'business_district_source.txt', 'caravan_membership_source.txt',
                 'route_source.txt', 'lane_source.txt',
                 'towing-relationship.json', 'towing_design_source.txt'):
        shutil.copyfile(roots[2] / name, stage / name)
    history = stage / 'caravan_history.jsonl'
    lines = history.read_text().splitlines()
    frame = json.loads(lines[0])
    frame['drawn_units'] = []
    lines[0] = json.dumps(frame)
    history.write_text('\n'.join(lines) + '\n')
    try:
        audit([roots[0], roots[1], stage])
    except ValueError as error:
        if 'drawn body changed' not in str(error):
            raise
        (PACKAGE / 'cases/towing-sweep-comparison-negative.log').write_text(
            'Expected rejection: ' + str(error) + '\n')
    else:
        raise AssertionError('Changed original drawn body accepted')
    print(json.dumps({'case_count': 3, 'frames_per_case': 900,
                      'receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
                      'changed_drawn_body_rejected': True}))


if __name__ == '__main__':
    main()
