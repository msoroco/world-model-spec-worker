"""Exercise delivery audit on retained fixture sources and one removed source."""
import argparse,json,tempfile
from pathlib import Path
from delivery_audit import audit
p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--negative',action='store_true');a=p.parse_args()
if not a.negative:
 print(json.dumps(audit(a.case,a.attempt),indent=2))
else:
 with tempfile.TemporaryDirectory(prefix='backing-delivery-negative-') as raw:
  staged=Path(raw)
  for source in Path(a.attempt).iterdir():
   if source.is_file() and source.name!='backing_history.jsonl':(staged/source.name).symlink_to(source.resolve())
  audit(a.case,staged)
