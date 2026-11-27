"""Engineering fallback: gentler route following, same designation and route."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def main():
    path=ROOT/'execution-manifest.json';manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].split('__')[-1]
        source=ROOT/entry['construction'];primary=json.loads(source.read_text())
        entry['construction_sha256']=sha(source)
        if entry.get('offline') or entry.get('compatibility'):
            raise ValueError('Do not invalidate proof-bearing entry')
        fallback=json.loads(json.dumps(primary))
        item=next(e for e in fallback['files'] if e['path']=='config.json')
        config=json.loads(item['content'])
        config['engineering_throttle']=.18
        config['engineering_braking_factor']=4.0
        item['content']=json.dumps(config,indent=2,ensure_ascii=False)+'\n'
        fallback_path=Path('cases')/suffix/'fallback1-construction.json'
        write(ROOT/fallback_path,fallback)
        entry['candidates']=[{'id':'fallback1','construction':str(fallback_path),
          'construction_sha256':sha(ROOT/fallback_path),
          'trigger':{'source':'original Native trace.jsonl and safety-zone-history.jsonl',
            'metric':'original route progress, body-to-zone overlap and marker camera coverage',
            'failure_condition':'primary misses the selected route target or original zone boundary and vehicle body are not observable through the encounter'},
          'changed_knobs':['engineering_throttle: 0.25 to 0.18',
                            'engineering_braking_factor: 5.0 to 4.0']}]
    write(path,manifest)
if __name__=='__main__':main()
