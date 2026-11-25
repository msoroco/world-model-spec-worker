"""Bind unselected driver-hand-signal draft to current CPU probe sources."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    draft=json.loads((HERE/'draft-preparing-hand-signal-manifest.json').read_text())
    batch=json.loads((ROOT/'batch.json').read_text())
    case=draft['cases'][0]
    probe={'format':'worker-execution-manifest',
           'assignment_id':HERE.name,'status':'partial','delivery_ready':False,
           'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
           'cases':[{'case_id':case['case_id'],'id':'primary','kind':'delivery',
                     'construction':case['construction'],
                     'construction_sha256':case['construction_sha256'],
                     'measurement_contract':'measurement-contracts/preparing_hand_signal.json',
                     'measurement_procedure':{'entrypoint':'finalize.py',
                                              'output_schema':'source-bound-emergency-abreast-v1'},
                     'candidate_risk':{'status':'physical',
                                       'reason':'Visible driver hand signal, authorization and flashing pixels require original source review'},
                     'candidates':case['candidates'],
                     'fixture_recipe':(HERE/'current-preparing_hand_signal-recipe.json').relative_to(ROOT).as_posix()}]}
    target=HERE/'current-hand-signal-probe-manifest.json'
    target.write_text(json.dumps(probe,indent=2)+'\n')
    print(json.dumps({'cases':1,'manifest':target.name},sort_keys=True))


if __name__=='__main__':main()
