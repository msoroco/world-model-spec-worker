"""Bind each exact config to its canonical source-observation inventory."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
BY_ID = {case['case_id']: case for case in CASES}


def main():
    for folder in (ROOT, *(ROOT / 'cases' / name for name in
                             ('through_entered', 'clear', 'no_slow'))):
        path = folder / 'config.json'
        config = json.loads(path.read_text())
        config['recording_description'] = BY_ID[config['selected_case_id']]['recording_description']
        path.write_text(json.dumps(config, indent=2) + '\n')
        print(config['selected_case_id'])


if __name__ == '__main__':
    main()
