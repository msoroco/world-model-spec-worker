"""Saved-only counterfactual of the exact right-pass case with opposite signal premise."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path.cwd()
PKG=ROOT/'work/heldout__C179789__NRS-484B-207-2__motor_vehicle_driver'
MANIFEST=PKG/'execution-manifest.json'
manifest=json.loads(MANIFEST.read_text())
entry=manifest['cases'][4]
case=entry['case_id']
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import materialize_case
from worker_exchange.saved_processing import prepare_video
prefix=ROOT/'.runtime-work/c179789-right-pass-counterfactual'
if prefix.exists():shutil.rmtree(prefix)
prefix.mkdir()
fixture=prefix/'fixture'
shutil.copytree(ROOT/'.runtime-work/c179789-current-4-primary-saved/fixture',fixture)
survey_path=fixture/'right_pass_road_survey.json'
survey=json.loads(survey_path.read_text())
if survey['subject_left_turn_signal_observed'] is not True or survey['diagnostic_fixture'] is not True:
    raise ValueError('Positive diagnostic survey premise differs')
survey['subject_left_turn_signal_observed']=False
survey_path.write_text(json.dumps(survey,indent=2)+'\n')
premise_path=fixture/'right_pass_premise.json'
premise=json.loads(premise_path.read_text())
premise['permission_state']=False
premise['road_survey_sha256']=hashlib.sha256(survey_path.read_bytes()).hexdigest()
premise_path.write_text(json.dumps(premise,indent=2)+'\n')
attempt=prefix/'attempt'
materialize_case(MANIFEST,case,attempt,fixture,'primary')
selection=attempt/'candidate-selection.json'
if selection.exists():
    value=json.loads(selection.read_text());value['manifest_sha256']=hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    selection.write_text(json.dumps(value,indent=2)+'\n')
prepare_video(attempt)
output=prefix/'output'
cmd=[str(ROOT/'.venv-cpu/bin/python'),'runtime.py','process-saved',
     '--manifest',str(MANIFEST),'--case',case,'--attempt',str(attempt),
     '--output',str(output),'--library','runtime/library',
     '--validator',str(ROOT/'.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
run=subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                   text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(prefix/'command.log').write_text(run.stdout)
if run.returncode:print(run.stdout[-2000:]);sys.exit(run.returncode)
receipt=output/'v0001/processing.json'
saved=json.loads(receipt.read_text())
if saved['missing_evidence'] or not saved['originals_preserved']:raise ValueError('Baseline saved source failed')
sys.path.insert(0,str(PKG))
from overtaken_saved_behavior_audit import audit_right_pass_exception
positive=audit_right_pass_exception(receipt,PKG/'right-pass-primary-saved-processing.json')
negative=[]
base_root=Path(saved['analysis_directory'])
for kind in ('missing_premise','contradictory_permission'):
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work') as temporary:
        stage=Path(temporary)
        for item in base_root.iterdir():
            if item.is_file():shutil.copyfile(item,stage/item.name)
        altered=json.loads(receipt.read_text())
        altered['analysis_directory']=str(stage)
        if kind=='missing_premise':
            (stage/'right_pass_premise.json').unlink()
        else:
            candidate=json.loads((stage/'right_pass_premise.json').read_text())
            candidate['permission_state']=True
            (stage/'right_pass_premise.json').write_text(json.dumps(candidate,indent=2)+'\n')
            altered['original_source_hashes']['right_pass_premise.json']=hashlib.sha256(
                (stage/'right_pass_premise.json').read_bytes()).hexdigest()
        altered_path=stage/'altered-receipt.json'
        altered_path.write_text(json.dumps(altered,indent=2)+'\n')
        try:audit_right_pass_exception(altered_path,PKG/'right-pass-primary-saved-processing.json')
        except ValueError as error:negative.append({'kind':kind,'rejected':True,'error':str(error)})
        else:raise ValueError('Counterfactual negative was accepted: '+kind)
proof={'format':'worker-right-pass-conditional-comparison-proof','case_id':case,
       'baseline_command':' '.join(cmd),'baseline_receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),
       'variant_receipt_sha256':hashlib.sha256((PKG/'right-pass-primary-saved-processing.json').read_bytes()).hexdigest(),
       'positive':positive,'negative':negative,'diagnostic_fixture_only':True,
       'actual_native_permission_status':'unverified',
       'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
(prefix/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
delivery_proof=PKG/'five-primary-delivery-proof.json'
combined=json.loads(delivery_proof.read_text())
combined['conditional_right_pass_comparison']=proof
delivery_proof.write_text(json.dumps(combined,indent=2)+'\n')
print('PASS exact-case conditional right-pass saved comparison',json.dumps(positive),flush=True)
