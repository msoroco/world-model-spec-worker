"""Add the exact towing diagnostic to the canonical case proposal."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CASE_ID = PACKAGE.name + '__towed_entrant_can_occupy_gap'


def main():
    path = PACKAGE / 'proposals/cases.json'
    value = json.loads(path.read_text())
    value['cases'] = [case for case in value['cases'] if case['case_id'] != CASE_ID]
    wide = next(case for case in value['cases'] if case['case_id'].endswith('__entrant_can_occupy_gap'))
    tow = deepcopy(wide)
    tow['case_id'] = CASE_ID
    tow['rationale'] = 'Diagnostic full drawing-and-drawn body gap and entrant occupancy; statutory danger remains unresolved.'
    tow['paired_probe_id'] = 'towing_gap_occupancy'
    construction = json.loads((PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json').read_text())
    tow['recording_description'] = construction['recording_description']
    value['cases'].append(tow)
    path.write_text(json.dumps(value, indent=2) + '\n')
    index_path = PACKAGE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    print(CASE_ID)


if __name__ == '__main__':
    main()
