import argparse,ast,json,sys,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port');a=p.parse_args()
if a.check:
 cfg=json.loads((ROOT/'native/config.json').read_text());assert cfg
 for f in (ROOT/'native').glob('*.py'):ast.parse(f.read_text())
 for f in (ROOT/'native').glob('*.xodr'):
  x=ET.parse(f).getroot();assert x.tag=='OpenDRIVE';assert x.findall('road')
 print(json.dumps({'offline_source_and_map_checks':True,'live_connection':False,'native_imports_and_visibility_unverified':True}))
else:
 if not all((a.output_dir,a.host,a.port)):p.error('Supply output directory, host and port')
 subprocess.run([sys.executable,str(ROOT/'native/runner.py'),'--output-dir',a.output_dir,'--host',a.host,'--port',a.port],check=True,cwd=ROOT/'native')
