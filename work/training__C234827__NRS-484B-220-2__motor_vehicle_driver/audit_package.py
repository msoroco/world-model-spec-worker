"""Independent exact-byte and copied CPU replay audit for rotary bundles."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder):
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check','--bundle',str(folder)],
                          text=True,capture_output=True,timeout=20)


def run_saved(bundle,saved):
    return subprocess.run([sys.executable,str(bundle/'measure_saved.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_triggers(bundle,saved):
    return subprocess.run([sys.executable,str(bundle/'triggers.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_comparison(bundle,first,second):
    return subprocess.run([sys.executable,str(bundle/'compare_saved.py'),str(first),str(second)],
                          text=True,capture_output=True,timeout=20)


def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text())
    proof=json.loads(proof_path.read_text())
    expected={(case,candidate) for case in ('reference','contrast')
              for candidate in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c234827-exact-offline-bundles-v1' or
            manifest['assignment_id']!=CASE.name or
            manifest['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['format']!='c234827-exact-compatibility-proof-v1' or
            proof['manifest_sha256']!=sha(manifest_path) or
            len(proof['positives'])!=8 or len(proof['negatives'])!=24 or
            len(proof.get('copied_saved_positives',[]))!=2 or
            len(proof.get('copied_saved_negatives',[]))!=2 or
            len(proof.get('copied_trigger_positives',[]))!=2 or
            len(proof.get('copied_trigger_negatives',[]))!=2 or
            len(proof.get('copied_comparison_positives',[]))!=1 or
            len(proof.get('copied_comparison_negatives',[]))!=1 or
            proof['copied_comparison_negatives'][0]['rejected'] is not True or
            not all(item['rejected'] is True for item in
                    proof['copied_saved_negatives']+proof['copied_trigger_negatives']) or
            any(not item['rejected'] for item in proof['negatives']) or
            manifest['accepted_originals_replayed']!=0 or
            proof['accepted_originals_replayed']!=0 or
            manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('Rotary package proof coverage differs')
    seen=set();checks=0;rejections=0;saved_checks=0;saved_rejections=0
    trigger_checks=0;trigger_rejections=0
    comparison_checks=0;comparison_rejections=0
    for entry in manifest['entries']:
        case=entry['case_id'].removeprefix(CASE.name+'__')
        candidate=entry['candidate_id']
        if (case,candidate) not in expected or (case,candidate) in seen:
            raise ValueError('Rotary package candidate coverage differs')
        seen.add((case,candidate))
        source=NATIVE/'drafts'/case/candidate
        folder=CASE/entry['bundle']
        mapping={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'road.xodr':NATIVE/'road.xodr',
            'island-geometry.json':NATIVE/'island-geometry.json',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'runner.py':NATIVE/'runner.py',
            'measure_saved.py':NATIVE/'measure_saved.py',
            'triggers.py':NATIVE/'triggers.py',
            'compare_saved.py':NATIVE/'compare_saved.py',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json'}
        if (entry['sha256']!={name:sha(folder/name) for name in mapping} or
                entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
                entry['status']!='unselected_native_request'):
            raise ValueError('Rotary copied source bytes differ')
        result=run(folder)
        if result.returncode!=0 or json.loads(result.stdout)['requested_frames']!=240:
            raise ValueError('Rotary copied CPU check differs')
        checks+=1
        for name in ('requested-tracks.jsonl','assignment-source.json','road.xodr'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise ValueError('Rotary changed copied source accepted')
                rejections+=1
        if candidate=='primary':
            saved=NATIVE/'saved-fixtures'/case
            measured=run_saved(folder,saved)
            routed=run_triggers(folder,saved)
            if measured.returncode!=0 or routed.returncode!=0:
                raise ValueError('Copied rotary saved or trigger processor failed')
            measurement=json.loads(measured.stdout)
            routing=json.loads(routed.stdout)
            saved_receipt=next(row for row in proof['copied_saved_positives']
                               if row['case_id']==entry['case_id'])
            trigger_receipt=next(row for row in proof['copied_trigger_positives']
                                 if row['case_id']==entry['case_id'])
            if (measurement['source_hashes']!=saved_receipt['source_hashes'] or
                    routing['source_hashes']!=trigger_receipt['source_hashes'] or
                    routing['selected_candidate'] is not None or
                    not measurement['half_circle_passage_observed']):
                raise ValueError('Copied rotary saved receipt differs')
            saved_checks+=1;trigger_checks+=1
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'saved';shutil.copytree(saved,altered)
                path=altered/'island-frames.jsonl'
                path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
                if run_saved(folder,altered).returncode==0:
                    raise ValueError('Copied rotary saved processor accepted missing frame')
                if run_triggers(folder,altered).returncode==0:
                    raise ValueError('Copied rotary trigger accepted missing frame')
                saved_rejections+=1;trigger_rejections+=1
            if case=='reference':
                contrast=NATIVE/'saved-fixtures'/'contrast'
                paired=run_comparison(folder,saved,contrast)
                if paired.returncode!=0:
                    raise ValueError('Copied rotary comparison failed')
                result=json.loads(paired.stdout)
                receipt=proof['copied_comparison_positives'][0]
                if (receipt['bundle']!=entry['bundle'] or
                        receipt['source_hashes']!=result['source_hashes'] or
                        result['paired_frames']!=240 or result['accepted_comparison']):
                    raise ValueError('Copied rotary comparison receipt differs')
                comparison_checks+=1
                with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                    altered=Path(temporary)/'contrast';shutil.copytree(contrast,altered)
                    path=altered/'island-readback.json'
                    path.write_bytes(path.read_bytes()+b' ')
                    if run_comparison(folder,saved,altered).returncode==0:
                        raise ValueError('Copied rotary comparison accepted changed island')
                    comparison_rejections+=1
    if seen!=expected:raise ValueError('Rotary package incomplete')
    receipt={'format':'c234827-independent-package-audit-v1',
        'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
        'bundles_checked':checks,'negative_rejections_replayed':rejections,
        'copied_saved_checks':saved_checks,
        'copied_saved_rejections_replayed':saved_rejections,
        'copied_trigger_checks':trigger_checks,
        'copied_trigger_rejections_replayed':trigger_rejections,
        'copied_comparison_checks':comparison_checks,
        'copied_comparison_rejections_replayed':comparison_rejections,
        'accepted_originals_replayed':0,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
