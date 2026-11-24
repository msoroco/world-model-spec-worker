"""Bind selected exit-side constructions to active runtime and fixture recipes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=json.loads((HERE/'draft-execution-manifest.json').read_text())
    source['runtime_manifest_sha256']=sha(ROOT/'runtime/SOURCE-MANIFEST.json')
    source['status']='delivery_prepared'
    for case in source['cases']:
        suffix=case['case_id'].rsplit('__',1)[-1]
        case['kind']='delivery'
        case['candidates']=case['candidates'][:2]
        case['fixture_recipe']=(HERE.relative_to(ROOT)/f'current-{suffix}-recipe.json').as_posix()
        contract=json.loads((HERE/'draft-candidates'/suffix/'measurement-contract.json').read_text())
        contract['format']='worker-measurement-contract'
        contract_path=HERE/'current-contracts'/f'{suffix}.json'
        contract_path.parent.mkdir(exist_ok=True)
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        case['measurement_contract']=contract_path.relative_to(HERE).as_posix()
        for item in [case]+case['candidates']:
            path=HERE/item['construction']
            bundle=json.loads(path.read_text())
            for f in bundle['files']:
                if f['path']=='finalize.py':f['content']=(HERE/'native/finalize.py').read_text()
            target=HERE/'current-bundles'/suffix/item['id']/'construction.json'
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(bundle,indent=2)+'\n')
            item['construction']=target.relative_to(HERE).as_posix()
            item['construction_sha256']=sha(target)
    out=HERE/'current-execution-manifest.json'
    out.write_text(json.dumps(source,indent=2)+'\n')
    print(json.dumps({'runtime':source['runtime_manifest_sha256'],
                      'cases':len(source['cases']),
                      'candidates':sum(1+len(c['candidates']) for c in source['cases'])}))


if __name__=='__main__':main()
