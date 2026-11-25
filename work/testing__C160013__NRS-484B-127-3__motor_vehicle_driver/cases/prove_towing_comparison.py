"""Exercise both sides of the independent towing comparison boundary."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from towing_comparison import audit


def main():
    plain = REPO / '.runtime-work/c160013-wide-compat-v11'
    drawn = REPO / '.runtime-work/c160013-towing-compat-v1'
    result = audit(plain, drawn)
    receipt = PACKAGE / 'cases/towing-comparison-diagnostic.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    stage = REPO / '.runtime-work/c160013-towing-comparison-negative'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    changed = stage / 'caravan_history.jsonl'
    changed.write_bytes((drawn / 'caravan_history.jsonl').read_bytes())
    for name in ('road_context.json', 'towing-relationship.json',
                 'towing_design_source.txt'):
        shutil.copy2(drawn / name, stage / name)
    for source in ('business_district_source.txt', 'caravan_membership_source.txt',
                   'route_source.txt', 'lane_source.txt'):
        shutil.copy2(drawn / source, stage / source)
    lines = changed.read_text().splitlines()
    first = json.loads(lines[0])
    first['drawn_units'] = []
    lines[0] = json.dumps(first)
    changed.write_text('\n'.join(lines) + '\n')
    try:
        audit(plain, stage)
    except ValueError as exc:
        if 'drawn body or link' not in str(exc):
            raise
        (PACKAGE / 'cases/towing-comparison-negative.log').write_text(
            'Expected rejection: ' + str(exc) + '\n')
    else:
        raise AssertionError('Changed original drawn body was accepted')
    print(json.dumps({'comparison_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
                      'frames_per_case': 900, 'changed_drawn_body_rejected': True,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
