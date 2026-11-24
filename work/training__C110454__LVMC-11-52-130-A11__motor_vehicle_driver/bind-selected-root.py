"""Bind the first current delivery case as the shared 11-case root implementation."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/'draft-current-primaries/witness_1/construction.json'


def clean(content):
    return '\n'.join(line.rstrip() for line in content.rstrip().splitlines())+'\n'


def main():
    plan=json.loads((HERE/'case-plan.json').read_text())
    ids=[case['case_id'] for case in plan['cases']]
    assert len(ids)==len(set(ids))==11
    for case in plan['cases']:
        case['kind']='delivery'
    (HERE/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    bundle=json.loads(ORIGINAL.read_text())
    bundle['status']='selected_delivery_root'
    for item in bundle['files']:
        if item['path']=='config.json':
            config=json.loads(item['content'])
            config['supported_case_ids']=ids
            item['content']=json.dumps(config,indent=2)+'\n'
        item['content']=clean(item['content'])
        path=HERE/item['path']
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(item['content'])
    (HERE/'construction.json').write_text(json.dumps(bundle,indent=2)+'\n')
    print(json.dumps({'selected_case_ids':len(ids),'root_files':len(bundle['files'])}))

if __name__=='__main__':
    main()
