"""Independently audit exact LVMC roundabout bundles and CPU replays."""
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
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check',
        '--bundle',str(folder)],text=True,capture_output=True,timeout=20)

def saved_run(folder,script,witness=None):
    cmd=[sys.executable,str(folder/script)]
    if witness:cmd.append(str(folder/'saved-fixtures'/witness))
    return subprocess.run(cmd,text=True,capture_output=True,timeout=20)

def prepared_run(folder,raw,output):
    return subprocess.run([sys.executable,str(folder/'prepare_raw.py'),
        '--bundle',str(folder),'--raw-folder',str(raw),'--output-dir',str(output),
        '--synthetic-cpu'],text=True,capture_output=True,timeout=20)


def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text())
    proof=json.loads(proof_path.read_text())
    expected={(w,c) for w in ('witness_1','witness_2')
              for c in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c234827-lvmc-exact-offline-v1' or
            manifest['assignment_id']!=CASE.name or
            manifest['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['format']!='c234827-lvmc-compatibility-proof-v1' or
            proof['manifest_sha256']!=sha(manifest_path) or
            len(proof['positives'])!=8 or len(proof['negatives'])!=24 or
            len(proof['saved_positives'])!=32 or len(proof['saved_negatives'])!=16 or
            any(not row['rejected'] for row in proof['negatives']) or
            manifest['accepted_originals_replayed']!=0 or
            proof['accepted_originals_replayed']!=0 or
            manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('LVMC package proof coverage differs')
    seen=set();checks=0;rejections=0;saved_checks=0;saved_rejections=0
    for entry in manifest['entries']:
        witness=entry['case_id'].removeprefix(CASE.name+'__')
        candidate=entry['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('LVMC package candidate coverage differs')
        seen.add((witness,candidate))
        source=NATIVE/'drafts'/witness/candidate
        folder=CASE/entry['bundle']
        mapping={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'road.xodr':NATIVE/'road.xodr',
            'island-geometry.json':NATIVE/'island-geometry.json',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'runner.py':NATIVE/'runner.py',
            'capture.py':NATIVE/'capture.py',
            'prepare_raw.py':NATIVE/'prepare_raw.py',
            'fixture_raw.py':NATIVE/'fixture_raw.py',
            'measure_saved.py':NATIVE/'measure_saved.py',
            'triggers.py':NATIVE/'triggers.py',
            'compare_saved.py':NATIVE/'compare_saved.py',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json'}
        for saved_witness in ('witness_1','witness_2'):
            for name in ('native-observed.jsonl','roundabout-readback.json','roundabout-frames.jsonl'):
                relative=f'saved-fixtures/{saved_witness}/{name}'
                mapping[relative]=NATIVE/relative
        if (entry['sha256']!={name:sha(folder/name) for name in mapping} or
                entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
                entry['status']!='unselected_native_request'):
            raise ValueError('LVMC copied source bytes differ')
        compile((folder/'capture.py').read_text(),str(folder/'capture.py'),'exec')
        result=run(folder)
        if result.returncode!=0 or json.loads(result.stdout)['requested_frames']!=240:
            raise ValueError('LVMC copied CPU check differs')
        checks+=1
        for script in ('measure_saved.py','triggers.py','compare_saved.py'):
            receipt=saved_run(folder,script,witness if script!='compare_saved.py' else None)
            if receipt.returncode!=0 or json.loads(receipt.stdout)['delivery_ready']:
                raise ValueError('Copied LVMC saved CPU check differs')
            saved_checks+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            base=Path(temporary);raw=base/'raw';saved=base/'saved'
            generated=subprocess.run([sys.executable,str(folder/'fixture_raw.py'),
                '--bundle',str(folder),'--output-dir',str(raw)],
                text=True,capture_output=True,timeout=20)
            if generated.returncode or prepared_run(folder,raw,saved).returncode:
                raise ValueError('Copied raw-to-saved replay failed')
            originals=[json.loads(x) for x in (raw/'native-raw-actors.jsonl').read_text().splitlines()]
            derived=[json.loads(x) for x in (saved/'native-observed.jsonl').read_text().splitlines()]
            if len(originals)!=240 or len(derived)!=240 or any(
                source['ego']['center_native_xyz_m'][:2]!=
                [target['ego_x_m'],target['ego_y_m']] or
                source['ego']['body_native_xyz_m'][0][:2]!=target['ego_body_xy_m'][0]
                for source,target in zip(originals,derived)):
                raise ValueError('Independent raw-to-saved coordinate join differs')
            receipt=json.loads((saved/'preparation-receipt.json').read_text())
            if receipt['delivery_ready'] or receipt['source_kind']!='synthetic_cpu':
                raise ValueError('Raw-to-saved replay overclaims readiness')
            saved_checks+=1
            path=raw/'roundabout-review.jsonl';lines=path.read_text().splitlines()
            row=json.loads(lines[27]);row['review_provenance']='human_frame_review'
            lines[27]=json.dumps(row);path.write_text('\n'.join(lines)+'\n')
            if prepared_run(folder,raw,base/'rejected').returncode==0:
                raise ValueError('Altered synthetic review accepted')
            saved_rejections+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'saved-fixtures'/witness/'roundabout-readback.json'
            changed=json.loads(path.read_text());changed['island_radius_m']=16
            path.write_text(json.dumps(changed)+'\n')
            for script in ('measure_saved.py','triggers.py','compare_saved.py'):
                if saved_run(altered,script,witness if script!='compare_saved.py' else None).returncode==0:
                    raise ValueError('Copied LVMC altered saved readback accepted')
            saved_rejections+=1
        for name in ('requested-tracks.jsonl','assignment-source.json','road.xodr'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise ValueError('LVMC changed copied source accepted')
                rejections+=1
    if seen!=expected:raise ValueError('LVMC package incomplete')
    receipt={'format':'c234827-lvmc-independent-package-audit-v1',
        'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
        'bundles_checked':checks,'negative_rejections_replayed':rejections,
        'saved_checks_replayed':saved_checks,
        'saved_negative_sources_replayed':saved_rejections,
        'accepted_originals_replayed':0,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
