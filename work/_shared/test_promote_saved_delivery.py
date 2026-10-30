"""CPU fixture: promote derived outputs once and reject changed originals."""
import hashlib,json,shutil
from pathlib import Path
from promote_saved_delivery import promote
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'.runtime-work/promotion-fixture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x)+'\n')
def test():
 if BASE.exists():shutil.rmtree(BASE)
 attempt=BASE/'recording/evidence';analysis=BASE/'processed/v0001/analysis';attempt.mkdir(parents=True);analysis.mkdir(parents=True)
 (attempt/'capture').mkdir()
 names=['trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',*(n+'.mkv' for n in ('overview','approach','reference_corner','driver_reference'))]
 for name in names:
  p=attempt/name;p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text('{"video_frame":0,"time_s":0.0}\n' if name=='video_frames.jsonl' else 'source '+name+'\n')
 put(analysis/'result.json',{'case_id':'test-case'})
 (analysis/'raw.mkv').write_bytes(b'derived primary')
 put(analysis/'traffic_spec/trace.json',{'scenes':[{'t':0}]})
 put(analysis/'four-view-receipt.json',{'format':'synchronized-four-view-v1',
  'sources':{name:sha(attempt/(name+'.mkv')) for name in ('overview','approach','reference_corner','driver_reference')},
  'frame_map_sha256':sha(attempt/'video_frames.jsonl'),'primary_sha256':sha(analysis/'raw.mkv'),'frames':1})
 put(BASE/'processed/v0001/processing.json',{'format':'worker-saved-processing-v2','case_id':'test-case',
  'passed':True,'recorded_only':True,'originals_preserved':True,'timestamp_joins':{'passed':True},
  'analysis_directory':str(analysis.resolve()),'result_sha256':sha(analysis/'result.json'),
  'final_video_checks':{'video_sha256':sha(analysis/'raw.mkv')},
  'original_source_hashes':{name:sha(attempt/name) for name in names}})
 report=promote(attempt,BASE/'processed/v0001','test-case',attempt/'promotion.json')
 assert report['originals_preserved'] and all((attempt/name).is_file() for name in ('result.json','raw.mkv','traffic_spec/trace.json','four-view-receipt.json'))
 (attempt/'overview.mkv').write_bytes(b'tampered')
 try:promote(attempt,BASE/'processed/v0001','test-case',attempt/'rejected.json')
 except ValueError as error:
  assert 'Sealed original differs' in str(error)
  print('negative rejected:',error)
 else:raise AssertionError('Changed original accepted')
 print('positive passed; derived files source-bound and originals preserved')
if __name__=='__main__':test()
