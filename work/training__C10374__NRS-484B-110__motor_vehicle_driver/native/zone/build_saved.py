"""Prepare and measure eight copied synthetic zone raw fixtures."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    copied=json.loads((HERE/'offline/manifest.json').read_text())
    entries=[]
    for entry in copied['entries']:
        bundle=HERE/entry['bundle'];suffix=bundle.parent.name;candidate=bundle.name
        raw=HERE/'offline/raw-fixtures'/suffix/candidate
        saved=HERE/'offline/saved-fixtures'/suffix/candidate
        for path in (raw,saved):
            if path.exists():shutil.rmtree(path)
        subprocess.run([sys.executable,str(bundle/'fixture_raw.py'),'--bundle',str(bundle),
            '--output-dir',str(raw)],check=True,capture_output=True,text=True)
        subprocess.run([sys.executable,str(bundle/'saved.py'),'--bundle',str(bundle),
            '--raw-folder',str(raw),'--saved-folder',str(saved),'--synthetic-cpu'],
            check=True,capture_output=True,text=True)
        m=subprocess.run([sys.executable,str(bundle/'saved.py'),'--bundle',str(bundle),
            '--saved-folder',str(saved)],check=True,capture_output=True,text=True)
        r=subprocess.run([sys.executable,str(bundle/'route_fallbacks.py'),
            '--bundle',str(bundle),'--saved',str(saved)],
            check=True,capture_output=True,text=True)
        measurement=json.loads(m.stdout);routing=json.loads(r.stdout)
        if measurement['source_kind']!='synthetic_cpu' or measurement['delivery_ready'] or \
           routing['selected_fallback'] is not None:
            raise ValueError('synthetic zone measurement promoted')
        entries.append({'case_id':entry['case_id'],'candidate_id':candidate,
            'raw_hashes':{p.name:sha(p) for p in raw.iterdir() if p.is_file()},
            'saved_hashes':{p.name:sha(p) for p in saved.iterdir() if p.is_file()},
            'measurement':measurement,'routing':routing})
    result={'format':'c10374-zone-synthetic-saved-v1',
        'copied_manifest_sha256':sha(HERE/'offline/manifest.json'),
        'entries':entries,'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/saved-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps({'cases':len(build()['entries'])}))
