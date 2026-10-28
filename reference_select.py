"""List source-hashed portable examples relevant to one frozen assignment."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def select(assignment_id):
    from hashlib import sha256
    assignment=json.loads((ROOT/'inputs'/assignment_id/'assignment.json').read_text())
    catalog=json.loads((ROOT/'references/catalog.json').read_text())
    cell=assignment.get('cell',{})
    features={str(cell.get(key,'')) for key in ('layout','maneuver','control')}-{'','travel'}
    exact=[]
    fallback=[]
    for item in catalog['items']:
        path=ROOT/item['path']
        if sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Reference changed: '+item['path'])
        if assignment['law_id'] in item.get('laws',[]):
            exact.append(item)
        elif features.intersection(item.get('scene_features',[])):
            fallback.append(item)
    return {'assignment_id':assignment_id,'references':exact or fallback,
            'scope':'Adaptation examples only; no testing evidence or physical acceptance'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assignment_id')
    args=parser.parse_args()
    print(json.dumps(select(args.assignment_id),indent=2))
