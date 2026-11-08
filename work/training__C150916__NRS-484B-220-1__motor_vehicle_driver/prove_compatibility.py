"""Execute eight copied CPU checks and reject altered exact bundle sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder):
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check','--bundle',str(folder)],
                          text=True,capture_output=True,timeout=20)


def run_saved(bundle, saved):
    return subprocess.run([sys.executable,str(bundle/'measure_saved.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_triggers(bundle,saved):
    return subprocess.run([sys.executable,str(bundle/'triggers.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_comparison(bundle, first, second):
    return subprocess.run([sys.executable,str(bundle/'compare_saved.py'),str(first),str(second)],
                          text=True,capture_output=True,timeout=20)


def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[];saved_positives=[];saved_negatives=[]
    trigger_positives=[];trigger_negatives=[]
    comparison_positives=[];comparison_negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if {name:sha(folder/name) for name in entry['sha256']}!=entry['sha256']:
            raise ValueError('One-way copied source differs from manifest')
        result=run(folder)
        if result.returncode!=0:raise AssertionError(result.stderr)
        receipt=json.loads(result.stdout)
        if receipt['requested_frames']!=240 or receipt['physical_sign_verified'] or receipt['delivery_ready']:
            raise AssertionError('One-way copied CPU check overclaimed')
        positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                          'config_sha256':sha(folder/'config.json'),'passed':True})
        for mutation,file in (('track_bytes','requested-tracks.jsonl'),
                              ('assignment_bytes','assignment-source.json'),
                              ('road_bytes','road.xodr')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/file;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError('One-way copied checker accepted '+mutation)
                negatives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                                  'mutation':mutation,'rejected':True})
        if entry['candidate_id']=='primary':
            case=entry['case_id'].removeprefix(CASE.name+'__')
            saved=CASE/'native'/'saved-fixtures'/case
            result=run_saved(folder,saved)
            if result.returncode!=0:raise AssertionError(result.stderr)
            measured=json.loads(result.stdout)
            if (measured['case']!=case or measured['direction_matches_designation']!=(case=='designated') or
                    measured['delivery_ready'] or measured['legal_verdict'] is not None):
                raise AssertionError('Copied one-way saved measurement differs')
            saved_positives.append({'case_id':entry['case_id'],
                                    'source_hashes':measured['source_hashes'],'passed':True})
            triggered=run_triggers(folder,saved)
            if triggered.returncode!=0:raise AssertionError(triggered.stderr)
            routing=json.loads(triggered.stdout)
            if (routing['source_hashes']!=measured['source_hashes'] or
                    routing['triggered']['fallback3_stop_before_entry'] is not True or
                    routing['selected_candidate'] is not None):
                raise AssertionError('Copied one-way trigger routing differs')
            trigger_positives.append({'case_id':entry['case_id'],
                                      'source_hashes':routing['source_hashes'],'passed':True})
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'saved';shutil.copytree(saved,altered)
                path=altered/'sign-frames.jsonl'
                path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
                if run_saved(folder,altered).returncode==0:
                    raise AssertionError('Copied one-way processor accepted missing sign frame')
                saved_negatives.append({'case_id':entry['case_id'],
                                        'mutation':'missing_sign_frame','rejected':True})
                if run_triggers(folder,altered).returncode==0:
                    raise AssertionError('Copied one-way triggers accepted missing sign frame')
                trigger_negatives.append({'case_id':entry['case_id'],
                                          'mutation':'missing_sign_frame','rejected':True})
            if case == 'designated':
                opposite=CASE/'native'/'saved-fixtures'/'opposite'
                pair=run_comparison(folder,saved,opposite)
                if pair.returncode!=0:raise AssertionError(pair.stderr)
                compared=json.loads(pair.stdout)
                if compared['paired_frames']!=240 or compared['accepted_comparison']:
                    raise AssertionError('Copied saved comparison differs')
                comparison_positives.append({'bundle':entry['bundle'],
                    'source_hashes':compared['source_hashes'],'passed':True})
                with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                    altered=Path(temporary)/'opposite';shutil.copytree(opposite,altered)
                    path=altered/'designation-record.json'
                    path.write_bytes(path.read_bytes()+b' ')
                    if run_comparison(folder,saved,altered).returncode==0:
                        raise AssertionError('Copied comparison accepted altered designation')
                    comparison_negatives.append({'mutation':'designation_bytes','rejected':True})
    result={'format':'c150916-exact-compatibility-proof-v1',
            'assignment_id':CASE.name,'manifest_sha256':sha(manifest_path),
            'positives':positives,'negatives':negatives,
            'copied_saved_positives':saved_positives,
            'copied_saved_negatives':saved_negatives,
            'copied_trigger_positives':trigger_positives,
            'copied_trigger_negatives':trigger_negatives,
            'copied_comparison_positives':comparison_positives,
            'copied_comparison_negatives':comparison_negatives,
            'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negatives'])}))
