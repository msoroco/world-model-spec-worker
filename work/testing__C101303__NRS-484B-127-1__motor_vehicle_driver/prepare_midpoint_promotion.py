"""Stage a nine-case manifest without altering the selected manifest."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    selected=json.loads((ROOT/'execution-manifest.json').read_text())
    draft=json.loads((ROOT/'midpoint-draft-manifest.json').read_text())
    case=draft['cases'][0]
    if len(selected['cases'])!=8 or len(draft['cases'])!=1:
        raise ValueError('Expected eight selected cases plus one midpoint')
    if case['case_id'] in {x['case_id'] for x in selected['cases']}:
        raise ValueError('Midpoint already selected')
    combined=dict(selected)
    combined['cases']=[*selected['cases'],case]
    (ROOT/'midpoint-promotion-candidate.json').write_text(json.dumps(combined,indent=2)+'\n')
    print(case['case_id'])


if __name__=='__main__':
    main()
