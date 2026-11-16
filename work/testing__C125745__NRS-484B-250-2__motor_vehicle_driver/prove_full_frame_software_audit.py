"""Recheck four synthetic full-frame attempts and two independent comparisons."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from audit_delivery import audit as delivery
from audit_comparisons import audit as comparisons

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(root):
 root=Path(root)
 names=['stop_ego_left_near_time','stop_ego_right_near_time',
        'stop_ego_left_separated','stop_opposite_left_turn']
 attempts={}
 proofs={}
 for name in names:
  path=root/name
  cfg=json.loads((path/'config.json').read_text())
  attempts[cfg['selected_case_id']]=path
  proof=delivery(path)
  if proof['original_frame_count']!=900 or proof['delivery_ready'] is not False:
   raise ValueError('Synthetic full-frame delivery boundary differs')
  decodes={}
  for camera in ('overview','approach','reference_corner','driver_reference'):
   command=['ffprobe','-v','error','-count_frames','-select_streams','v:0',
      '-show_entries','stream=nb_read_frames','-of','default=nokey=1:noprint_wrappers=1',
      str(path/(camera+'.mkv'))]
   count=int(subprocess.check_output(command,text=True).strip())
   if count!=900:raise ValueError('Synthetic video decode count differs')
   decodes[camera]=count
  proofs[name]={'audit':proof,'decoded_frames':decodes}
 compare=comparisons(HERE,attempts)
 if compare['software_comparisons_passed'] is not True or compare['delivery_ready'] is not False:
  raise ValueError('Synthetic comparison boundary differs')
 return {'format':'worker-c125745-full-frame-software-proof','diagnostic_fixture_only':True,
         'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
         'cases':proofs,'comparisons':compare,
         'fixture_builder_sha256':sha(HERE/'build_full_frame_fixture.py'),
         'delivery_auditor_sha256':sha(HERE/'audit_delivery.py'),
         'comparison_auditor_sha256':sha(HERE/'audit_comparisons.py')}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt-root',required=True,type=Path)
 a=p.parse_args();print(json.dumps(run(a.attempt_root),indent=2))
