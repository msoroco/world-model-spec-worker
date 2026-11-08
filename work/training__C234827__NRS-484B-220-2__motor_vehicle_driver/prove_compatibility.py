"""Execute all copied rotary CPU checks and altered-source controls."""
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


def run_saved(bundle,saved):
    return subprocess.run([sys.executable,str(bundle/'measure_saved.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_triggers(bundle,saved):
    return subprocess.run([sys.executable,str(bundle/'triggers.py'),str(saved)],
                          text=True,capture_output=True,timeout=20)


def run_comparison(bundle,first,second):
    return subprocess.run([sys.executable,str(bundle/'compare_saved.py'),str(first),str(second)],
                          text=True,capture_output=True,timeout=20)


def run_preparation(bundle,raw,review,output):
    return subprocess.run([sys.executable,str(bundle/'prepare_rotary.py'),
        '--raw-folder',str(raw),'--review',str(review),
        '--config',str(bundle/'config.json'),'--output',str(output)],
        text=True,capture_output=True,timeout=20)


def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[];saved_positives=[];saved_negatives=[]
    trigger_positives=[];trigger_negatives=[]
    comparison_positives=[];comparison_negatives=[]
    preparation_positives=[];preparation_negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('Copied rotary bundle bytes differ')
        result=run(folder)
        if result.returncode!=0:raise AssertionError(result.stderr)
        checked=json.loads(result.stdout)
        if checked['requested_frames']!=240 or checked['delivery_ready']:
            raise AssertionError('Copied rotary checker overclaims readiness')
        positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],
            'config_sha256':sha(folder/'config.json'),'passed':True})
        for mutation,name in (('track_bytes','requested-tracks.jsonl'),
                              ('assignment_bytes','assignment-source.json'),
                              ('road_bytes','road.xodr')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError('Copied rotary altered source accepted')
                negatives.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],
                    'mutation':mutation,'rejected':True})
        if entry['candidate_id']=='primary':
            case=entry['case_id'].removeprefix(CASE.name+'__')
            fixture=CASE/'native'/'preparation-fixtures'/case
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                prepared=Path(temporary)/'saved'
                result=run_preparation(folder,fixture/'raw',fixture/'review.json',prepared)
                if result.returncode!=0:raise AssertionError(result.stderr)
                receipt=json.loads(result.stdout)
                if receipt['delivery_ready'] or receipt['source_kind']!='synthetic_cpu':
                    raise AssertionError('Copied rotary preparer overclaims readiness')
                preparation_positives.append({'case_id':entry['case_id'],
                    'saved_hashes':receipt['saved_hashes'],'passed':True})
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'raw';shutil.copytree(fixture/'raw',altered)
                path=altered/'video_frames.jsonl'
                path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
                if run_preparation(folder,altered,fixture/'review.json',
                                   Path(temporary)/'saved').returncode==0:
                    raise AssertionError('Copied rotary preparer accepted missing video frame')
                preparation_negatives.append({'case_id':entry['case_id'],
                    'mutation':'missing_video_frame','rejected':True})
            saved=CASE/'native'/'saved-fixtures'/case
            measurement=run_saved(folder,saved)
            routing=run_triggers(folder,saved)
            if measurement.returncode!=0 or routing.returncode!=0:
                raise AssertionError('Copied rotary saved processing failed')
            measured=json.loads(measurement.stdout)
            routed=json.loads(routing.stdout)
            if (measured['case']!=case or not measured['half_circle_passage_observed'] or
                    routed['source_hashes']!=measured['source_hashes'] or
                    routed['selected_candidate'] is not None):
                raise AssertionError('Copied rotary saved or routing result differs')
            saved_positives.append({'case_id':entry['case_id'],
                'source_hashes':measured['source_hashes'],'passed':True})
            trigger_positives.append({'case_id':entry['case_id'],
                'source_hashes':routed['source_hashes'],'passed':True})
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'saved';shutil.copytree(saved,altered)
                path=altered/'island-frames.jsonl'
                path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
                if run_saved(folder,altered).returncode==0:
                    raise AssertionError('Copied rotary saved processor accepted missing frame')
                if run_triggers(folder,altered).returncode==0:
                    raise AssertionError('Copied rotary trigger accepted missing frame')
                saved_negatives.append({'case_id':entry['case_id'],
                    'mutation':'missing_camera_frame','rejected':True})
                trigger_negatives.append({'case_id':entry['case_id'],
                    'mutation':'missing_camera_frame','rejected':True})
            if case=='reference':
                contrast=CASE/'native'/'saved-fixtures'/'contrast'
                paired=run_comparison(folder,saved,contrast)
                if paired.returncode!=0:raise AssertionError(paired.stderr)
                result=json.loads(paired.stdout)
                if result['paired_frames']!=240 or result['accepted_comparison']:
                    raise AssertionError('Copied rotary comparison differs')
                comparison_positives.append({'bundle':entry['bundle'],
                    'source_hashes':result['source_hashes'],'passed':True})
                with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                    altered=Path(temporary)/'contrast';shutil.copytree(contrast,altered)
                    path=altered/'island-readback.json'
                    path.write_bytes(path.read_bytes()+b' ')
                    if run_comparison(folder,saved,altered).returncode==0:
                        raise AssertionError('Copied rotary comparison accepted changed island')
                    comparison_negatives.append({'mutation':'island_readback','rejected':True})
    proof={'format':'c234827-exact-compatibility-proof-v1',
        'assignment_id':CASE.name,'manifest_sha256':sha(manifest_path),
        'positives':positives,'negatives':negatives,
        'copied_saved_positives':saved_positives,
        'copied_saved_negatives':saved_negatives,
        'copied_trigger_positives':trigger_positives,
        'copied_trigger_negatives':trigger_negatives,
        'copied_comparison_positives':comparison_positives,
        'copied_comparison_negatives':comparison_negatives,
        'copied_preparation_positives':preparation_positives,
        'copied_preparation_negatives':preparation_negatives,
        'accepted_originals_replayed':0,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negatives'])}))
