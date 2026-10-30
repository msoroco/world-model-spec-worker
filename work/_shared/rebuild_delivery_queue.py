"""Bind reviewed v7 order to exact v3 delivery and saved-only handoffs."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
QUEUE=ROOT/'work/_shared/gpu-queue.json'

def write(value):QUEUE.write_text(json.dumps(value,indent=2)+'\n')

def main():
 queue=json.loads(QUEUE.read_text())
 queue['native_executed']=0
 queue['video_core_accepted']=0
 queue['comparison_complete']=0
 entries={}
 for folder in (ROOT/'work').glob('testing__*'):
  path=folder/'execution-manifest.json'
  if not path.is_file():continue
  for item in json.loads(path.read_text())['cases']:
   entries[(folder.name,item['case_id'])]=item
 for row in queue['cases']:
  aid,case=row['assignment_id'],row['case_id']
  entry=entries[(aid,case)]
  row['capture_command']=entry['gpu_command']
  row['postprocessing_command']=entry['post_capture']['command']
  row['owner_release_command']=entry['owner_release_command']+' # exact case '+case
  row['delivery_promotion_command']=(
   'python3.11 work/_shared/promote_saved_delivery.py --case '+case+
   ' --attempt "$CANONICAL_ATTEMPT" --processed "$PROCESSED_VERSION"'+
   ' --output "$CANONICAL_ATTEMPT/delivery-promotion.json"')
  row['delivery_audit_command']=entry['delivery_acceptance']['command']
  row['canonical_recording_reuse']=['demo-test','full-test']
 for row in queue['comparison_audit_commands']:
  row['command']=row['command'].replace('work/_shared/runtime002.py','work/_shared/runtime-v3.py')
 queue['processing_order']=['capture-only Native command','actual resource owner release by local operator',
  'owner-release acknowledgement','selected saved processing into vNNNN',
  'hash-checked derived-evidence promotion into canonical attempt',
  'independent delivery audit on saved evidence','refresh saved analysis indexes',
  'source and comparison audits']
 write(queue)
 print(len(queue['cases']),len(queue['comparison_audit_commands']))

if __name__=='__main__':main()
