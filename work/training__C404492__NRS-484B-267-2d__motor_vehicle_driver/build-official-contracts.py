"""Bind the two regulatory draft cases to the exact source-only measurement method."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    source=json.loads((HERE/'measurement-contracts/controlled_1.json').read_text())
    for suffix in ('official_1','official_2'):
        contract=dict(source)
        contract['case_id']=HERE.name+'__'+suffix
        target=HERE/'measurement-contracts'/(suffix+'.json')
        target.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
        print(target.name)


if __name__=='__main__':main()
