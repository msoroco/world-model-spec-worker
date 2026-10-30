"""Promote verified saved-processing outputs into one canonical attempt.

Only absent derived files are added. Original Native acquisition is never edited.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

VIEWS=('overview','approach','reference_corner','driver_reference')
DERIVED=('result.json','raw.mkv','traffic_spec/trace.json','four-view-receipt.json')

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as source:
  for chunk in iter(lambda:source.read(1048576),b''):h.update(chunk)
 return h.hexdigest()

def read(path):return json.loads(path.read_text())

def require(ok,message):
 if not ok:raise ValueError(message)

def promote(attempt,processed,case,output):
 attempt=attempt.resolve();processed=processed.resolve();output=output.resolve()
 require(attempt.is_dir() and processed.is_dir(),'Canonical attempt or saved version missing')
 require(output.parent==attempt and not output.exists(),'Promotion receipt must be new inside canonical attempt')
 receipt=read(processed/'processing.json');analysis=processed/'analysis'
 require(receipt.get('format')=='worker-saved-processing-v2' and receipt.get('case_id')==case
         and receipt.get('passed') is True and receipt.get('recorded_only') is True
         and receipt.get('originals_preserved') is True and receipt.get('timestamp_joins',{}).get('passed') is True,
         'Saved processing is incomplete or selects another case')
 originals=receipt.get('original_source_hashes',{})
 for relative in ('trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',*(view+'.mkv' for view in VIEWS)):
  source=attempt/relative
  require(source.is_file() and originals.get(relative)==sha(source),'Sealed original differs from saved processing: '+relative)
 require(analysis.is_dir() and Path(receipt.get('analysis_directory','')).resolve()==analysis,
         'Saved analysis directory differs from receipt')
 result=analysis/'result.json';raw=analysis/'raw.mkv';core=analysis/'traffic_spec/trace.json'
 require(all(p.is_file() for p in (result,raw,core,analysis/'four-view-receipt.json')),
         'Saved processing omits required derived delivery evidence')
 require(sha(result)==receipt.get('result_sha256') and
         sha(raw)==receipt.get('final_video_checks',{}).get('video_sha256'),
         'Derived result or primary video differs from saved processing')
 composition=read(analysis/'four-view-receipt.json')
 require(composition.get('format')=='synchronized-four-view-v1'
         and composition.get('frame_map_sha256')==sha(attempt/'video_frames.jsonl')
         and composition.get('primary_sha256')==sha(raw)
         and composition.get('sources')=={view:sha(attempt/(view+'.mkv')) for view in VIEWS},
         'Four-view composition does not bind original sources')
 scenes=read(core).get('scenes',[])
 mapping=[json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines() if line.strip()]
 require(len(scenes)==len(mapping)==composition.get('frames') and all(
         row.get('video_frame')==i and scene.get('t')==round(row['time_s']*1000)
         for i,(row,scene) in enumerate(zip(mapping,scenes))),
         'Core trace does not join original frame times')
 hashes={}
 for relative in DERIVED:
  source=analysis/relative;target=attempt/relative;target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():
   require(sha(target)==sha(source),'Existing canonical evidence differs: '+relative)
  else:
   with source.open('rb') as origin,target.open('xb') as destination:
    shutil.copyfileobj(origin,destination)
  hashes[relative]=sha(target)
 report={'format':'worker-saved-delivery-promotion-v1','case_id':case,
         'processing_sha256':sha(processed/'processing.json'),
         'original_hashes':{name:sha(attempt/name) for name in originals if (attempt/name).is_file()},
         'derived_hashes':hashes,'originals_preserved':True,'physical_acceptance_claimed':False}
 output.write_text(json.dumps(report,indent=2)+'\n')
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True)
 p.add_argument('--processed',type=Path,required=True);p.add_argument('--case',required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(promote(a.attempt,a.processed,a.case,a.output),indent=2))

if __name__=='__main__':main()
