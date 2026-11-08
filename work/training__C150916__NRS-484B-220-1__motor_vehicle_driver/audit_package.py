"""Independent byte-source and subprocess replay audit of C150916 bundles."""
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


def run_comparison(bundle, first, second):
    return subprocess.run([sys.executable,str(bundle/'compare_saved.py'),str(first),str(second)],
                          text=True,capture_output=True,timeout=20)


def run_preparation(bundle, base, output):
    return subprocess.run([sys.executable,str(bundle/'prepare_one_way.py'),
        '--raw-folder',str(base/'raw'),'--review',str(base/'sign-review.json'),
        '--designation',str(base/'designation-source.json'),
        '--config',str(bundle/'config.json'),'--output',str(output)],
        text=True,capture_output=True,timeout=20)


def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text());proof=json.loads(proof_path.read_text())
    expected={(case,candidate) for case in ('designated','opposite')
              for candidate in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c150916-exact-offline-bundles-v1' or
            manifest['assignment_id']!=CASE.name or
            manifest['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['format']!='c150916-exact-compatibility-proof-v1' or
            proof['manifest_sha256']!=sha(manifest_path) or
            any(item['delivery_ready'] or item['original_native_observed'] for item in (manifest,proof)) or
            len(proof['positives'])!=8 or len(proof['negatives'])!=24 or
            len(proof.get('copied_saved_positives',[]))!=2 or
            len(proof.get('copied_saved_negatives',[]))!=2 or
            len(proof.get('copied_trigger_positives',[]))!=2 or
            len(proof.get('copied_trigger_negatives',[]))!=2 or
            len(proof.get('copied_comparison_positives',[]))!=1 or
            len(proof.get('copied_comparison_negatives',[]))!=1 or
            proof['copied_comparison_negatives'][0]['rejected'] is not True or
            len(proof.get('copied_preparation_positives',[]))!=2 or
            len(proof.get('copied_preparation_negatives',[]))!=2 or
            not all(item['rejected'] is True for item in proof['copied_preparation_negatives']) or
            not all(item['rejected'] is True for item in proof['copied_trigger_negatives']) or
            not all(item['rejected'] is True for item in proof['copied_saved_negatives']) or
            not all(item['rejected'] is True for item in proof['negatives'])):
        raise ValueError('One-way offline proof provenance or coverage differs')
    seen=set();checks=0;rejections=0;saved_checks=0;saved_rejections=0
    trigger_checks=0;trigger_rejections=0
    comparison_checks=0;comparison_rejections=0
    preparation_checks=0;preparation_rejections=0
    for entry in manifest['entries']:
        case=entry['case_id'].removeprefix(CASE.name+'__');candidate=entry['candidate_id']
        if (case,candidate) not in expected or (case,candidate) in seen:
            raise ValueError('One-way bundle case coverage differs')
        seen.add((case,candidate))
        folder=CASE/entry['bundle']
        source=NATIVE/'drafts'/case/candidate
        mapping={'config.json':source/'config.json',
                 'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                 'road.xodr':NATIVE/'road.xodr',
                 'measurement-contract.json':NATIVE/'measurement-contract.json',
                 'runner.py':NATIVE/'runner.py',
                 'measure_saved.py':NATIVE/'measure_saved.py',
                 'compare_saved.py':NATIVE/'compare_saved.py',
                 'prepare_one_way.py':NATIVE/'prepare_one_way.py',
                 'triggers.py':NATIVE/'triggers.py',
                 'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                 'case-plan.json':CASE/'case-plan.json'}
        if (entry['bundle']!=str(folder.relative_to(CASE)) or
                entry['status']!='unselected_native_request' or
                entry['sha256']!={name:sha(folder/name) for name in mapping} or
                entry['sha256']!={name:sha(path) for name,path in mapping.items()}):
            raise ValueError('One-way copied bytes differ from source')
        result=run(folder)
        if result.returncode!=0 or json.loads(result.stdout)['requested_frames']!=240:
            raise ValueError('One-way copied CPU check failed')
        checks+=1
        for file in ('requested-tracks.jsonl','assignment-source.json','road.xodr'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/file;path.write_bytes(path.read_bytes()+b'\n')
                if run(altered).returncode==0:
                    raise ValueError('One-way altered copied source accepted')
                rejections+=1
        if candidate=='primary':
            saved=NATIVE/'saved-fixtures'/case
            base=NATIVE/'preparation-fixtures'/case
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                made=run_preparation(folder,base,Path(temporary)/'prepared')
                if made.returncode!=0:
                    raise ValueError('Copied one-way preparer failed: '+made.stderr)
                receipt=next(item for item in proof['copied_preparation_positives']
                             if item['case_id']==entry['case_id'])
                prepared=json.loads(made.stdout)
                if (prepared['source_kind']!='synthetic_cpu' or
                        prepared['saved_hashes']!=receipt['saved_hashes'] or
                        prepared['measurement']['case']!=case):
                    raise ValueError('Copied one-way preparation receipt differs')
                preparation_checks+=1
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'fixture';shutil.copytree(base,altered)
                path=altered/'raw'/'forward-video-stub.txt'
                path.write_bytes(path.read_bytes()+b'changed')
                if run_preparation(folder,altered,Path(temporary)/'prepared').returncode==0:
                    raise ValueError('Copied one-way preparer accepted changed video')
                preparation_rejections+=1
            result=run_saved(folder,saved)
            if result.returncode!=0:
                raise ValueError('Copied one-way saved processor failed: '+result.stderr)
            measured=json.loads(result.stdout)
            receipt=next(item for item in proof['copied_saved_positives']
                         if item['case_id']==entry['case_id'])
            if (measured['source_hashes']!=receipt['source_hashes'] or
                    measured['direction_matches_designation']!=(case=='designated') or
                    measured['delivery_ready']):
                raise ValueError('Copied one-way saved measurement differs')
            saved_checks+=1
            triggered=run_triggers(folder,saved)
            expected_trigger=next(item for item in proof['copied_trigger_positives']
                                  if item['case_id']==entry['case_id'])
            if triggered.returncode!=0:
                raise ValueError('Copied one-way triggers failed: '+triggered.stderr)
            routing=json.loads(triggered.stdout)
            if (routing['source_hashes']!=expected_trigger['source_hashes'] or
                    routing['triggered']['fallback3_stop_before_entry'] is not True or
                    routing['selected_candidate'] is not None):
                raise ValueError('Copied one-way trigger result differs')
            trigger_checks+=1
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'saved';shutil.copytree(saved,altered)
                path=altered/'sign-frames.jsonl'
                path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
                if run_saved(folder,altered).returncode==0:
                    raise ValueError('Copied one-way saved processor accepted missing sign frame')
                saved_rejections+=1
                if run_triggers(folder,altered).returncode==0:
                    raise ValueError('Copied one-way triggers accepted missing sign frame')
                trigger_rejections+=1
            if case=='designated':
                opposite=NATIVE/'saved-fixtures'/'opposite'
                result=run_comparison(folder,saved,opposite)
                if result.returncode!=0:
                    raise ValueError('Copied one-way comparison failed: '+result.stderr)
                measured=json.loads(result.stdout)
                receipt=proof['copied_comparison_positives'][0]
                if (receipt['bundle']!=entry['bundle'] or
                        receipt['source_hashes']!=measured['source_hashes'] or
                        measured['paired_frames']!=240 or measured['accepted_comparison']):
                    raise ValueError('Copied one-way comparison receipt differs')
                comparison_checks+=1
                with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                    altered=Path(temporary)/'opposite';shutil.copytree(opposite,altered)
                    path=altered/'designation-record.json'
                    path.write_bytes(path.read_bytes()+b' ')
                    if run_comparison(folder,saved,altered).returncode==0:
                        raise ValueError('Copied one-way comparison accepted changed designation')
                    comparison_rejections+=1
    if seen!=expected:raise ValueError('One-way offline bundle coverage incomplete')
    receipt={'format':'c150916-independent-package-audit-v1',
             'assignment_id':CASE.name,'manifest_sha256':sha(manifest_path),
             'proof_sha256':sha(proof_path),'bundles_checked':checks,
             'negative_rejections_replayed':rejections,
             'copied_saved_checks':saved_checks,
             'copied_saved_rejections_replayed':saved_rejections,
             'copied_trigger_checks':trigger_checks,
             'copied_trigger_rejections_replayed':trigger_rejections,
             'copied_comparison_checks':comparison_checks,
             'copied_comparison_rejections_replayed':comparison_rejections,
             'copied_preparation_checks':preparation_checks,
             'copied_preparation_rejections_replayed':preparation_rejections,
             'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
