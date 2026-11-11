"""Run copied C132497 request and saved positives plus altered-source controls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(folder,script,args):
    return subprocess.run([sys.executable,str(folder/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[];saved_positives=[];saved_negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('C132497 copied bytes differ')
        request=run(folder,'check.py',['--bundle',folder])
        if request.returncode or json.loads(request.stdout)['delivery_ready']:
            raise AssertionError('C132497 copied request rejected or overclaimed: '+request.stderr)
        positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
            'config_sha256':sha(folder/'config.json'),'passed':True})
        measured=run(folder,'measure_saved.py',[folder])
        if measured.returncode or json.loads(measured.stdout)['delivery_ready']:
            raise AssertionError('C132497 copied saved rejected or overclaimed: '+measured.stderr)
        saved_positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],'passed':True})
        routed=run(folder,'triggers.py',[folder])
        if routed.returncode or json.loads(routed.stdout)['delivery_ready']:
            raise AssertionError('C132497 copied trigger rejected or overclaimed: '+routed.stderr)
        saved_positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],'script':'triggers.py','passed':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw';prepared=Path(temporary)/'prepared'
            fixture=run(folder,'fixture_raw.py',['--bundle',folder,'--output-dir',raw])
            if fixture.returncode:raise AssertionError('C132497 raw fixture failed: '+fixture.stderr)
            converted=run(folder,'prepare_raw.py',['--bundle',folder,
                '--raw-folder',raw,'--output-dir',prepared,'--synthetic-cpu'])
            measured_prepared=run(folder,'measure_prepared.py',
                ['--bundle',folder,'--saved-dir',prepared])
            if (converted.returncode or measured_prepared.returncode or
                json.loads(converted.stdout)['delivery_ready'] or
                json.loads(measured_prepared.stdout)['delivery_ready']):
                raise AssertionError('C132497 raw-to-saved proof failed: '+
                    converted.stderr+measured_prepared.stderr)
            saved_positives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'script':'prepare_raw.py + measure_prepared.py','passed':True})
            lines=(raw/'video_frames.jsonl').read_text().splitlines()
            row=json.loads(lines[71]);row['native_frame']+=1
            lines[71]=json.dumps(row)
            (raw/'video_frames.jsonl').write_text('\n'.join(lines)+'\n')
            if run(folder,'prepare_raw.py',['--bundle',folder,'--raw-folder',raw,
                '--output-dir',Path(temporary)/'altered','--synthetic-cpu']).returncode==0:
                raise AssertionError('C132497 changed raw video join accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'mutation':'raw_video_frame','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw'
            if run(folder,'fixture_raw.py',['--bundle',folder,'--output-dir',raw]).returncode:
                raise AssertionError('C132497 raw fixture missing')
            (raw/'controller-intention.json').unlink()
            if run(folder,'prepare_raw.py',['--bundle',folder,'--raw-folder',raw,
                '--output-dir',Path(temporary)/'missing-intention','--synthetic-cpu']).returncode==0:
                raise AssertionError('C132497 missing controller intention accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'mutation':'missing_controller_intention','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw'
            if run(folder,'fixture_raw.py',['--bundle',folder,'--output-dir',raw]).returncode:
                raise AssertionError('C132497 raw fixture missing')
            if run(folder,'prepare_raw.py',['--bundle',folder,'--raw-folder',raw,
                '--output-dir',Path(temporary)/'original']).returncode==0:
                raise AssertionError('C132497 missing original FFV1 media accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'mutation':'missing_original_media','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'saved'/'camera-frames.jsonl'
            lines=path.read_text().splitlines();row=json.loads(lines[71]);row['camera_frame']+=1
            lines[71]=json.dumps(row);path.write_text('\n'.join(lines)+'\n')
            if run(altered,'measure_saved.py',[altered]).returncode==0:
                raise AssertionError('C132497 changed saved camera join accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'mutation':'camera_frame','rejected':True})
            if run(altered,'triggers.py',[altered]).returncode==0:
                raise AssertionError('C132497 changed trigger camera join accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'mutation':'trigger_camera_frame','rejected':True})
        for mutation,name in (('track','requested-tracks.jsonl'),
            ('assignment','assignment-source.json'),('road','right-exit-road.xodr'),
            ('plan','case-plan.json'),('intention','controller-intention.json')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered,'check.py',['--bundle',altered]).returncode==0:
                    raise AssertionError('C132497 changed source accepted: '+mutation)
                negatives.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],'mutation':mutation,'rejected':True})
    proof={'format':'c132497-compatibility-proof-v1',
        'manifest_sha256':sha(manifest_path),'positives':positives,
        'negatives':negatives,'saved_positives':saved_positives,
        'saved_negatives':saved_negatives,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    x=prove();print(json.dumps({'positives':len(x['positives']),
        'negatives':len(x['negatives']),'saved_positives':len(x['saved_positives']),
        'saved_negatives':len(x['saved_negatives'])}))
