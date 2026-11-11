"""Independently audit C132497 bundle bytes, geometry and CPU replays."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def run(bundle,script,args):
    return subprocess.run([sys.executable,str(bundle/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def audit():
    manifest_path=CASE/'offline'/'manifest.json';proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text());proof=json.loads(proof_path.read_text())
    expected={(w,c) for w in ('reference','contrast')
        for c in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c132497-exact-offline-v1' or
        manifest['assignment_id']!=CASE.name or
        manifest['construction_sha256']!=sha(NATIVE/'manifest.json') or
        proof['manifest_sha256']!=sha(manifest_path) or
        len(proof['positives'])!=8 or len(proof['negatives'])!=40 or
        len(proof['saved_positives'])!=24 or len(proof['saved_negatives'])!=40 or
        manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('C132497 proof coverage differs')
    road=ET.parse(NATIVE/'right-exit-road.xodr').getroot()
    nodes={int(x.attrib['id']):x for x in road.findall('road')}
    if set(nodes)!={20,21,22,23}:raise ValueError('C132497 map roads differ')
    geo={ident:node.find('./planView/geometry') for ident,node in nodes.items()}
    if (abs(float(geo[20].attrib['x']))>1e-9 or
        abs(float(geo[20].attrib['y'])+52)>1e-9 or
        abs(float(geo[21].attrib['y'])+22)>1e-9 or
        abs(float(geo[22].attrib['x'])-22)>1e-9 or
        abs(float(geo[23].attrib['x'])-22)>1e-9 or
        abs(float(geo[23].attrib['y']))>1e-9 or
        abs(float(geo[21].find('arc').attrib['curvature'])+1/22)>1e-9 or
        abs(float(geo[23].find('arc').attrib['curvature'])+1/22)>1e-9 or
        abs(float(geo[21].attrib['length'])+float(geo[23].attrib['length'])-44*math.pi)>1e-8 or
        {int(x.attrib['id']) for x in road.findall('junction')}!={100,101}):
        raise ValueError('C132497 clockwise route geometry differs')
    seen=set();checks=0;rejections=0;saved_checks=0;saved_rejections=0;frames=0
    for entry in manifest['entries']:
        witness=entry['case_id'].removeprefix(CASE.name+'__');candidate=entry['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('C132497 candidate coverage differs')
        seen.add((witness,candidate));bundle=CASE/entry['bundle']
        source=NATIVE/'drafts'/witness/candidate
        mapping={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'controller-intention.json':source/'controller-intention.json',
            'right-exit-road.xodr':NATIVE/'right-exit-road.xodr',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'check.py':NATIVE/'check.py','measure_saved.py':NATIVE/'measure_saved.py',
            'triggers.py':NATIVE/'triggers.py',
            'prepare_raw.py':NATIVE/'prepare_raw.py',
            'fixture_raw.py':NATIVE/'fixture_raw.py',
            'measure_prepared.py':NATIVE/'measure_prepared.py',
            'capture.py':NATIVE/'capture.py',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json'}
        for name in ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json'):
            mapping['saved/'+name]=NATIVE/'saved-fixtures'/witness/candidate/name
        if (entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
            entry['sha256']!={name:sha(bundle/name) for name in mapping}):
            raise ValueError('C132497 copied source bytes differ')
        compile((bundle/'capture.py').read_text(),str(bundle/'capture.py'),'exec')
        checked=run(bundle,'check.py',['--bundle',bundle])
        measured=run(bundle,'measure_saved.py',[bundle])
        if checked.returncode or measured.returncode:
            raise ValueError('C132497 copied CPU replay failed')
        m=json.loads(measured.stdout)
        if m['delivery_ready'] or m['phase_frames']['entry']+m['phase_frames']['circulation']+m['phase_frames']['exit']!=240:
            raise ValueError('C132497 copied measurement differs')
        checks+=1;saved_checks+=1;frames+=240
        routed=run(bundle,'triggers.py',[bundle])
        if routed.returncode or json.loads(routed.stdout)['delivery_ready']:
            raise ValueError('C132497 copied trigger replay differs')
        saved_checks+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw';prepared=Path(temporary)/'prepared'
            if run(bundle,'fixture_raw.py',['--bundle',bundle,'--output-dir',raw]).returncode:
                raise ValueError('C132497 copied raw fixture differs')
            converted=run(bundle,'prepare_raw.py',['--bundle',bundle,
                '--raw-folder',raw,'--output-dir',prepared,'--synthetic-cpu'])
            measured_raw=run(bundle,'measure_prepared.py',
                ['--bundle',bundle,'--saved-dir',prepared])
            if converted.returncode or measured_raw.returncode:
                raise ValueError('C132497 copied raw conversion differs')
            converted_data=json.loads(converted.stdout)
            prepared_data=json.loads(measured_raw.stdout)
            source=rows(raw/'native-raw-actors.jsonl')
            saved_rows=rows(prepared/'native-observed.jsonl')
            if (converted_data['delivery_ready'] or prepared_data['delivery_ready'] or
                not (len(source)==len(saved_rows)==240)):
                raise ValueError('C132497 raw CPU proof overclaims or lacks frames')
            for a,b in zip(source,saved_rows):
                if (b['ego_x_m']!=a['ego']['center_native_xyz_m'][0] or
                    b['ego_y_m']!=a['ego']['center_native_xyz_m'][1] or
                    b['ego_actor_id']!=a['ego']['actor_id'] or
                    b['road_id']!=a['observed_road_id'] or
                    b['lane_id']!=a['observed_lane_id'] or
                    b['ego_body_xy_m']!=[p[:2] for p in a['ego']['body_native_xyz_m']]):
                    raise ValueError('C132497 raw-to-saved coordinates differ')
            saved_checks+=1
            review=raw/'right-lane-review.jsonl'
            lines=review.read_text().splitlines();line=json.loads(lines[71])
            line['review_provenance']='human_frame_review';lines[71]=json.dumps(line)
            review.write_text('\n'.join(lines)+'\n')
            if run(bundle,'prepare_raw.py',['--bundle',bundle,'--raw-folder',raw,
                '--output-dir',Path(temporary)/'bad','--synthetic-cpu']).returncode==0:
                raise ValueError('C132497 changed raw review accepted')
            saved_rejections+=1
            fresh=Path(temporary)/'fresh_raw'
            if run(bundle,'fixture_raw.py',['--bundle',bundle,'--output-dir',fresh]).returncode:
                raise ValueError('C132497 second raw fixture differs')
            if run(bundle,'prepare_raw.py',['--bundle',bundle,'--raw-folder',fresh,
                '--output-dir',Path(temporary)/'missing_media']).returncode==0:
                raise ValueError('C132497 original mode accepted missing FFV1 media')
            saved_rejections+=1
            (fresh/'controller-intention.json').unlink()
            if run(bundle,'prepare_raw.py',['--bundle',bundle,'--raw-folder',fresh,
                '--output-dir',Path(temporary)/'missing_intention','--synthetic-cpu']).returncode==0:
                raise ValueError('C132497 raw source without controller intention accepted')
            saved_rejections+=1
        for name in ('requested-tracks.jsonl','assignment-source.json',
                     'right-exit-road.xodr','case-plan.json','controller-intention.json'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(bundle,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered,'check.py',['--bundle',altered]).returncode==0:
                    raise ValueError('C132497 altered request source accepted')
                rejections+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(bundle,altered)
            path=altered/'saved'/'lane-readback.json'
            d=json.loads(path.read_text());d['right_lane_id']=-1
            path.write_text(json.dumps(d)+'\n')
            if run(altered,'measure_saved.py',[altered]).returncode==0:
                raise ValueError('C132497 altered saved lane readback accepted')
            saved_rejections+=1
            if run(altered,'triggers.py',[altered]).returncode==0:
                raise ValueError('C132497 altered trigger lane readback accepted')
            saved_rejections+=1
    if seen!=expected:raise ValueError('C132497 bundle set incomplete')
    receipt={'format':'c132497-independent-package-audit-v1',
        'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
        'bundles_checked':checks,'request_frames_recomputed':frames,
        'request_negative_rejections_replayed':rejections,
        'saved_checks_replayed':saved_checks,'saved_negative_rejections_replayed':saved_rejections,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
